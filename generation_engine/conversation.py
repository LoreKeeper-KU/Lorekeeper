"""Conversation references that survive the model's recent-message window."""

from copy import deepcopy
import re

from canon_memory.memory import entity_names
from .models import ConversationState


def update_context(request, canon):
    previous = request.conversation
    state = (deepcopy(previous) if previous and previous.world_id == request.world_id
             else ConversationState(request.world_id))
    pending = request.pending_canon
    referenced = list(canon)
    if pending and pending.world_id == request.world_id:
        referenced.extend(pending.facts)
    known = {f.subject for f in referenced}
    state.focus_entity_ids = [subject for subject in state.focus_entity_ids if subject in known]
    aliases = entity_names(referenced)

    def mentioned(text):
        return sorted({subject for name, subjects in aliases.items()
                       if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text.casefold())
                       for subject in subjects if subject in known})

    explicit = mentioned(request.message)
    if explicit:
        state.focus_entity_ids = explicit
    elif not state.focus_entity_ids:
        # Upgrade an existing chat which predates explicit conversation state.
        for turn in reversed(request.history):
            if turn.world_id == request.world_id and turn.kind != "error":
                found = mentioned(turn.content)
                if found:
                    state.focus_entity_ids = found
                    break
    return state

