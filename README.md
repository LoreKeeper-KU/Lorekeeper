# LoreKeeper

## Run the UI

From the repository root:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Chat workflow

Use the same message box to create characters, write scenes, ask questions,
and revise earlier replies. For example:

1. `Create Mira, a thief with black hair who wants to steal the vault key.`
2. Review the character draft, then reply `approve` to save its facts (or
   describe a change, or reply `discard`). Drafts are not accepted canon.
3. `Write a scene where Mira steals the vault key.`
4. `Why did Mira use her left hand?`
5. `Make it shorter.` edits the referenced reply. Say `Make the scene shorter`
   to revise the scene after discussing it.

Scenes and scene revisions run through verification and contradiction repair.
The reply's **Canon checks** expander shows the backend's reports. Explanations
use the referenced text and approved canon without claiming to be verified scenes.
Character creation and explanations do not load the continuity model.

To add lore to a saved character, say `Add a fact that Darth Vader was once
Anakin Skywalker`. LoreKeeper prepares an actual canon proposal and shows it
before saving. Confirm with `yes`, `I approve this change`, or similar wording;
reject it with `don't save that`. Corrections to existing facts preserve their
revision history. `What do we have in the database?` lists approved SQLite facts,
not an AI reconstruction of the conversation.

Ask `Generate a portrait of Darth Vader` or `Illustrate that scene` for artwork.
Image requests use saved canon and the existing image/vision backend. The image
is displayed in chat with expandable checks; failures and uncertain checks are
reported without claiming success. This needs configured image-generation and
vision-model access. Asking whether images are available does not generate one.

The backend entry point is `generation_engine.ui_backend.handle_message(ChatRequest)`.
`chat_orchestrator.py` runs a native function-calling conversation loop with automatic
(tool-optional) selection. Greetings, general discussion and edits to explanations can
be answered directly. When needed, the assistant can call `read_canon`,
`create_character`, `propose_canon`, `approve_canon`, `discard_canon`, `write_scene`,
and `generate_image`, see the actual result, and continue within the same turn.
There is no preliminary intent classifier or UI-selected action.

`chat_tools.py` validates arguments, binds all operations to the active world, and
keeps scene verification inside `write_scene`. Approvals require an unchanged proposal
shown on an earlier turn and an explicit confirmation in the latest user message.
The loop has an eight-round limit and preserves successful operations when a later
step fails. The configured text provider must support Chat Completions function tools;
`shared.ai_client.AIClient.chat_with_tools` uses `tool_choice="auto"`.
Protocol reference: [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling).

Canon persists in SQLite. The MVP uses `world_001`; requests and retrieval carry
the world ID explicitly. Conversation history and pending draft context live in
the browser session. **New chat** clears that context but keeps approved canon.
Up to 20 recent turns plus the active scene are supplied to the routing model;
older conversation history is not a durable story memory.

The session also tracks the currently discussed entities and unfinished fact-update
request separately from that message window. For example, `Change her hair color`
followed by `silver` can continue the same task without repeating the character's
name. Explicitly naming another character changes the focus. `Never mind` cancels
the unfinished task; **New chat** clears this conversation state. This context is
not approved canon and is never saved as world facts automatically.
