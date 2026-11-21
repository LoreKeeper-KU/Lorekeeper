# Authored by Faris
# Integration changes by Abdullah on 21/11/2026
"""The pieces of a LoreKeeper chat reply.

Generated text (scene, claims, reasons) is always shown through plain st.markdown. The small
HTML fragments here are built from constants, numbers and html-escaped text only.
"""

from html import escape

import streamlit as st

from lorekeeper_ui.presentation import (
    canon_check,
    claim_repair_state,
    classification_label,
    classification_slug,
    find_image,
    repair_steps,
    was_repaired,
)

ASSISTANT_AVATAR = "🛡️"
USER_AVATAR = ":material/person:"

CLASSIFICATION_ICONS = {
    "SUPPORTED": "✅",
    "CONTRADICTION": "❌",
    "VALID_NEW_ADDITION": "➕",
    "UNCERTAIN": "❓",
}

# (VerificationSummary field, classification, singular, plural) in display order.
COUNTS = (
    ("supported", "SUPPORTED", "supported", "supported"),
    ("contradictions", "CONTRADICTION", "contradiction", "contradictions"),
    ("valid_new_additions", "VALID_NEW_ADDITION", "new addition", "new additions"),
    ("uncertain", "UNCERTAIN", "uncertain", "uncertain"),
)


def html(markup: str) -> None:
    """Render trusted markup. Only ever pass constants, numbers or text through text()."""
    st.markdown(markup, unsafe_allow_html=True)


def text(value: str) -> str:
    return escape(value, quote=False)


def scene_card(key: str, scene_text: str, title: str = "Scene", chip: str = "") -> None:
    with st.container(border=True, key=key):
        html(f'<div class="lk-scene__meta"><span class="lk-eyebrow">{text(title)}</span>{chip}</div>')
        st.markdown(scene_text)


def canon_check_block(check) -> None:
    html(f'<div class="lk-canon lk-canon--{check.tone}">🛡 Canon Check — {text(check.headline)}</div>')


def steps_block(steps) -> None:
    items = "".join(
        f'<li class="lk-step lk-step--{step.state}">{text(step.label)}</li>' for step in steps
    )
    html(f'<ol class="lk-steps">{items}</ol>')


def classification_chip(value: str) -> str:
    return (
        f'<span class="lk-chip lk-chip--{classification_slug(value)}">'
        f"{CLASSIFICATION_ICONS[value]} {classification_label(value)}</span>"
    )


def claim_card(key: str, assessment, repair_state) -> None:
    chips = classification_chip(assessment.classification.value)
    if repair_state == "repaired":
        chips += '<span class="lk-chip lk-chip--repaired">🔧 Repaired in the final scene</span>'
    elif repair_state == "unresolved":
        chips += '<span class="lk-chip lk-chip--unresolved">⚠ Still unresolved</span>'
    facts = "".join(
        f'<code class="lk-fact">{text(fact_id)}</code>' for fact_id in assessment.evidence_fact_ids
    ) or '<span class="lk-muted">none cited</span>'

    with st.container(border=True, key=key):
        html(f'<div class="lk-claim__meta">{chips}</div>')
        st.markdown(f"**{assessment.claim}**")
        st.markdown(assessment.reason)
        html(f'<div class="lk-evidence"><span class="lk-evidence__label">Evidence fact IDs</span>{facts}</div>')


def pass_header(number: int, report) -> None:
    where = "Original generation" if number == 1 else f"After repair {number - 1}"
    counts = ""
    for field, classification, singular, plural in COUNTS:
        count = getattr(report.summary, field)
        word = singular if count == 1 else plural
        zero = " lk-count--zero" if count == 0 else ""
        counts += (
            f'<span class="lk-count lk-count--{classification_slug(classification)}{zero}">'
            f"{count} {word}</span>"
        )
    html(
        f'<div class="lk-pass"><span class="lk-pass__title">Pass {number} · {where}</span>'
        f'<span class="lk-counts">{counts}</span></div>'
    )


def verification_details(index: int, result) -> None:
    with st.expander("View verification details"):
        for number, report in enumerate(result.reports, start=1):
            pass_header(number, report)
            if not report.claims:
                st.caption("No claims were found in this pass.")
            for position, assessment in enumerate(report.claims):
                slug = classification_slug(assessment.classification.value)
                claim_card(
                    f"claim-{slug}-{index}-{number}-{position}",
                    assessment,
                    claim_repair_state(result, number - 1, assessment),
                )


def artwork(result) -> None:
    """The concept artwork, or a designed placeholder until the pipeline provides an image."""
    image = find_image(result)
    if image:
        html('<div class="lk-eyebrow lk-artwork__title">Concept artwork</div>')
        st.image(image)
        return
    html(
        '<div class="lk-artwork lk-artwork--empty"><span class="lk-artwork__icon">🖼</span>'
        '<span class="lk-artwork__copy"><strong>Concept artwork</strong>'
        "<span>Artwork for this scene will appear here once visual generation is connected.</span>"
        "</span></div>"
    )


#def render_result(index: int, result) -> None:
def render_result(
    index: int,
    result,
    show_artwork: bool = True,
) -> None:
    check = canon_check(result)
    repaired = was_repaired(result)
    chip = ""
    if repaired:
        label = "🔧 Repaired" if check.tone == "verified" else "✎ Revised"
        chip = f'<span class="lk-chip lk-chip--repaired">{label}</span>'

    # The final scene is the main result; the original generation stays one click away.
    scene_card(f"scene-{index}", result.final_scene.text, chip=chip)
    canon_check_block(check)
    steps = repair_steps(result)
    if steps:
        steps_block(steps)
    if result.reports:
        verification_details(index, result)
    if repaired:
        with st.expander("View original generation"):
            scene_card(f"original-{index}", result.initial_scene.text, title="Original generation")
    #artwork(result)
    if show_artwork:
        artwork(result)


def render_message(index: int, message: dict) -> None:
    if message["role"] == "user":
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(message["content"])
        return
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        render_reply(index, message)


def render_reply(index: int, message: dict) -> None:
    if "error" in message:
        st.error(f"LoreKeeper couldn't finish this request. {message['error']}")
    else:
        render_result(index, message["result"])
