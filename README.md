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

The backend entry point is `generation_engine.ui_backend.handle_message(ChatRequest)`.
It routes in `chat_orchestrator.py` before calling Abdullah's character creator
or scene pipeline. The UI supplies the message, world ID, prior turns, active
scene ID, and any pending draft; it does not choose an action. The router and
generation use the configured `AIClient`. Verified scenes also need the local
NLI model and its dependencies.

Canon persists in SQLite. The MVP uses `world_001`; requests and retrieval carry
the world ID explicitly. Conversation history and pending draft context live in
the browser session. **New chat** clears that context but keeps approved canon.
Up to 20 recent turns plus the active scene are supplied to the routing model;
older conversation history is not a durable story memory.
