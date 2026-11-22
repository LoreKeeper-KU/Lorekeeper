"""Validated tool boundary for the conversational assistant."""

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from canon_memory.canon_store import CanonStore
from canon_memory.memory import retrieve_canon
from canon_memory.canon_retriever import retrieve_by_entities
from shared.schemas import CanonFact
from shared.ai_client import AIClientError
from .canon_editor import FactChange, FactChanges, prepare_fact_changes
from .models import DemoRequest, PendingCanon
from .ui_backend import run_ui_request, readable_canon
from .ai_story_generator import AIStoryGenerator


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadCanon(Arguments):
    query: str = Field(description="Names or topic to look up. Empty string lists all saved canon.")


class CreateCharacter(Arguments):
    prompt: str = Field(min_length=1, description="The user's character request, with references resolved.")


class ProposeCanon(Arguments):
    changes: list[FactChange] = Field(min_length=1)


class ApproveCanon(Arguments):
    proposal_token: str
    confirmation_quote: str = Field(min_length=1, description="Exact words from the latest user message approving the displayed proposal.")


class DiscardCanon(Arguments):
    pass


class SceneRequest(Arguments):
    instruction: str = Field(min_length=1)
    target_message_id: str = Field(description="Existing scene message to revise/continue; empty for a new scene.")
    operation: Literal["generate_scene", "revise"]


class ImageRequest(Arguments):
    prompt: str = Field(min_length=1)
    target_message_id: str = Field(description="Scene to illustrate, or empty for a character portrait.")


TOOLS = {
    "read_canon": (ReadCanon, "Read approved facts in the active world. Use for database questions and before proposing edits. No writes."),
    "create_character": (CreateCharacter, "Create a structured character draft using the existing creator. Does NOT approve it. Empty worlds are allowed."),
    "propose_canon": (ProposeCanon, "Stage explicit author facts/edits for review. Use exact subjects/fact IDs from read_canon. Never invent a missing value. Does NOT save accepted canon."),
    "approve_canon": (ApproveCanon, "Approve the proposal shown on an earlier turn, only when the latest user message explicitly confirms it. Cannot approve a proposal created in this turn."),
    "discard_canon": (DiscardCanon, "Discard the pending proposal/unfinished task when the user cancels. Does not delete approved facts."),
    "write_scene": (SceneRequest, "Generate or revise a story scene through canon retrieval, verification and repair. Use for scene writing, not ordinary explanations or shortening an explanation."),
    "generate_image": (ImageRequest, "Generate and check artwork using saved canon. Call only for an explicit image request, not questions about availability. Requires image/vision API access."),
}


def definitions():
    return [{"type": "function", "function": {
        "name": name, "description": description, "parameters": schema.model_json_schema(),
    }} for name, (schema, description) in TOOLS.items()]


class ChatTools:
    def __init__(self, request, reply, history, client, comparator_factory):
        self.request, self.reply, self.history = request, reply, history
        self.client, self.comparator_factory = client, comparator_factory
        self.store = CanonStore()
        self.by_id = {turn.id: turn for turn in history if turn.role == "assistant"}
        pending = reply.pending_canon
        self.approvable = pending.proposal_ids[:] if pending and pending.message_id in self.by_id else []
        self.token = (pending.message_id or (pending.proposal_ids[0] if pending.proposal_ids else "")) if pending else ""
        self.new_proposal_text = ""
        self.events = []
        self.artifact_text = ""
        self.failure_notices = []
        self.image_failure = None

    def context(self):
        state = self.reply.conversation
        return {
            "message": self.request.message,
            "history": [{"role": t.role, "content": t.content} for t in self.history[-20:]],
            "conversation_state": {"original_request": state.task_request,
                                   "focus_entity_ids": state.focus_entity_ids},
        }

    def facts(self, query):
        found = retrieve_canon(query, world_id=self.request.world_id)
        if not found and self.reply.conversation.focus_entity_ids:
            found = retrieve_by_entities(self.store, self.request.world_id,
                                         self.reply.conversation.focus_entity_ids)
        return found

    def stage(self, pending, preview):
        if self.new_proposal_text and self.reply.pending_canon:
            earlier = self.reply.pending_canon
            if {f.id for f in pending.facts}.intersection(f.id for f in earlier.facts):
                return {"error": "This turn already proposed a change to that fact. Present the pending proposal first."}
            pending.facts = [*earlier.facts, *pending.facts]
            pending.proposal_ids = [*earlier.proposal_ids, *pending.proposal_ids]
            pending.name = ", ".join(dict.fromkeys([earlier.name, pending.name]))
            preview = self.new_proposal_text + "\n" + preview
        pending.message_id = self.reply.message.id
        self.reply.pending_canon = pending
        self.reply.conversation.focus_entity_ids = sorted({f.subject for f in pending.facts})
        self.reply.conversation.unfinished_task = "approve_canon"
        self.reply.conversation.task_request = self.request.message
        self.new_proposal_text = preview
        if self.reply.message.pipeline is None:
            self.reply.message.kind = "canon_proposal"
        return {"status": "pending_approval", "facts": [f.model_dump() for f in pending.facts],
                "preview": preview, "instruction": "Show the full proposed changes and ask for approval. Not saved canon."}

    def execute(self, name, arguments):
        if name not in TOOLS:
            return {"error": "Unknown tool. Choose an available tool or reply directly."}
        args = TOOLS[name][0].model_validate(arguments)
        if name == "generate_image" and self.image_failure:
            return self.image_failure
        world = self.request.world_id
        if name == "read_canon":
            facts = self.facts(args.query) if args.query.strip() else self.store.get_facts_by_world(world)
            if args.query.strip() and facts:
                self.reply.conversation.focus_entity_ids = sorted({f.subject for f in facts})
            return {"status": "read", "facts": [f.model_dump() for f in facts]}

        if name == "create_character":
            draft = run_ui_request(DemoRequest(args.prompt, world_id=world),
                                   self.store.get_facts_by_world(world), self.client, action="create_character")
            facts = [CanonFact.model_validate(f.model_dump()) for f in draft.proposed_facts]
            pending = PendingCanon(world, draft.profile.name, facts,
                                   [self.store.propose_update(world, f) for f in facts])
            preview = "\n".join(f"- {f.predicate.replace('_', ' ')}: {f.object}" for f in facts)
            return self.stage(pending, preview)

        if name == "propose_canon":
            pending, preview = prepare_fact_changes(self.context(), world, FactChanges(changes=args.changes))
            if pending is None:
                self.reply.conversation.unfinished_task = "propose_canon"
                self.reply.conversation.task_request = self.request.message
                self.reply.conversation.last_question = preview
                return {"status": "not_proposed", "detail": preview}
            return self.stage(pending, preview)

        if name == "approve_canon":
            pending = self.reply.pending_canon
            text = self.request.message.casefold()
            affirmative = re.search(r"\b(yes|approve|approved|confirm|confirmed|save|sure|go ahead|do it)\b", text)
            qualified = re.search(r"\b(no|not|never|don't|dont|wait|but|instead|if)\b|\?", text)
            if (pending is None or pending.world_id != world or not self.approvable
                    or pending.proposal_ids != self.approvable or args.proposal_token != self.token
                    or args.confirmation_quote.casefold() not in text or not affirmative or qualified):
                return {"error": "Approval requires a previously displayed, unchanged proposal and explicit unconditional confirmation in the latest user message. Nothing was saved."}
            self.store.approve_updates(pending.proposal_ids, world_id_filter=world)
            self.reply.pending_canon = None
            self.reply.conversation.focus_entity_ids = sorted({f.subject for f in pending.facts})
            self.clear_task()
            self.approvable = []
            summary = f"Saved {pending.name}'s facts to canon."
            self.events.append(summary)
            return {"status": "saved", "summary": summary, "facts": [f.model_dump() for f in pending.facts]}

        if name == "discard_canon":
            self.reply.pending_canon = None
            self.new_proposal_text = ""
            self.approvable = []
            self.clear_task()
            self.events.append("Discarded the pending proposal; approved canon was unchanged.")
            return {"status": "discarded", "summary": self.events[-1]}

        target = self.by_id.get(args.target_message_id)
        if args.target_message_id and (target is None or target.kind != "scene"):
            return {"error": "That scene reference is unavailable. Use a listed scene message ID or ask which scene."}
        scene = (target.pipeline.final_scene.text if target and target.pipeline else target.content if target else "")
        instruction = args.instruction if name == "write_scene" else args.prompt
        facts = self.facts(instruction + "\n" + scene)
        if not facts:
            return {"error": "No approved canon matched. Ask which saved character to use or offer to draft a new one."}
        if name == "write_scene":
            if args.operation == "revise" and not target:
                return {"error": "A scene revision needs an existing scene message ID."}
            story = AIStoryGenerator(self.client)
            context = dict(self.context(), message=instruction, target_reply=scene or None, referenced_scene=scene or None)
            comparator = self.comparator_factory() if self.comparator_factory else None
            team = run_ui_request(DemoRequest(instruction, world_id=world), facts, self.client,
                                  comparator=comparator,
                                  generate=lambda _prompt, canon: story.respond(args.operation, context, canon))
            self.reply.message.pipeline = team.text
            self.reply.message.kind = "scene"
            self.reply.message.source_scene_id = target.id if target else None
            self.reply.active_scene_id = self.reply.message.id
            self.artifact_text = team.text.final_scene.text
            self.by_id[self.reply.message.id] = self.reply.message
            return {"status": team.text.status, "scene": self.artifact_text,
                    "scene_message_id": self.reply.message.id,
                    "instruction": "Include the scene verbatim; do not rewrite verified text. Explain needs_review honestly."}

        from multimodal.visuals import generate_visual, check_visual_facts, build_visual_report
        from .team_pipeline import coverage_issues
        readable = readable_canon(facts)
        self.reply.message.asset = generate_visual(json.dumps({"request": instruction, "scene": scene}), readable, ai=self.client)
        self.reply.message.visual_status = "error"  # Remains explicit if vision fails.
        checks = check_visual_facts(self.reply.message.asset, readable, ai=self.client)
        report = build_visual_report(self.reply.message.asset, readable, checks)
        notes = coverage_issues(readable, checks) + report.issues
        self.reply.message.visual_notes = notes
        self.reply.message.visual_status = "needs_review" if notes or not report.consistent else "no_mismatches_detected"
        return {"status": self.reply.message.visual_status, "image_created": True,
                "issues": notes, "instruction": "The UI displays the image automatically. Do not invent an image URL."}

    def report_failure(self, name, error):
        detail = error.public_message if isinstance(error, AIClientError) else (
            "The image file could not be read or saved. Check output-directory permissions."
            if isinstance(error, OSError) else f"The operation failed ({type(error).__name__})."
        )
        if name == "generate_image":
            created = self.reply.message.asset is not None
            stage = "Image verification" if created else "Image generation"
            notice = f"{stage} failed: {detail}"
            self.reply.message.visual_status = "error"
            self.reply.message.visual_notes = [notice]
            output = {"error": notice, "image_created": created,
                      "instruction": "Explain this specific error. Do not retry image generation in this turn."}
            self.image_failure = output
        else:
            notice = f"{name.replace('_', ' ')} failed: {detail}"
            output = {"error": notice}
        self.failure_notices.append(notice)
        return output

    def clear_task(self):
        state = self.reply.conversation
        state.unfinished_task = state.task_request = state.last_question = ""
