# Renderer architecture

- [Current Rust / pygame architecture](current.html)
- [Accepted multi-renderer design](proposed.html)
- [Assessment and migration details](../../rendering-architecture-assessment.md)

The current diagram cites commit 65941ef0bc31016bb610591e95ac0ded4ba03ea7. Both diagrams passed Archify schema, showcase geometry and browser checks; light/dark 1440×900 captures were inspected. The proposed interfaces were a design when these diagrams were authored. Implementation status is documented separately as work proceeds.

The [2026-10-11 acceptance assessment](../../render-adapters-acceptance/README.md) maps this design to the implementation and records its initial findings. The subsequent [acceptance fixes](../../render-adapters-fixes/README.md) separate desktop UI IDs from authority and correct PNG encoding. Renderer-independent authority identity and Agent response comparisons now pass.

JSON sources accompany the standalone HTML. Original local receipts/captures remain under ignored .archify/; generated review artifacts are not project modules.
