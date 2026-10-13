# Phase 14: Install/Update Engine Correctness & Default-Shell Action - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-13
**Phase:** 14-install-update-engine-correctness-default-shell-action-selec
**Areas discussed:** Unificación de la ruta de update, Mensaje cuando no hace nada, Confirmación y guardrails de 'set default shell', Dónde vive la acción de shell

---

## Unificación de la ruta de update

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-update via UpdateTarget/service.run | La confirmación del batch cuenta como consentimiento; mismo motor y gate que `u` | ✓ |
| Solo avisar, no actuar | `resolve_dependencies` sigue excluyendo la tool, emite warning explícito | |
| Preguntar en el momento (nueva confirmación) | Modal aparte antes del batch si hay outdated seleccionadas | |

**User's choice:** Auto-update via UpdateTarget/service.run (Recomendado)
**Notes:** Confirmado sin objeciones — reutiliza el mecanismo ya probado por `action_update_tool`/`u`, tratando la confirmación de batch existente como consentimiento suficiente (D-01 del propio código de `catalog_tui.py`).

---

## Mensaje cuando no hace nada (bloqueo por ownership/mutation-grade gate)

| Option | Description | Selected |
|--------|-------------|----------|
| Agregado al resumen final del batch | Se acumula y aparece en `render_summary`/`render_failure_details`, mismo texto de razón que `u` | ✓ |
| Aviso individual en caliente durante el run | Cada tool bloqueada muestra su mensaje apenas se evalúa | |

**User's choice:** Agregado al resumen final del batch (Recomendado)
**Notes:** Coherente con el patrón post-hoc que `run_wizard` ya usa para reportar resultados del batch.

---

## Confirmación y guardrails de 'set default shell'

| Option | Description | Selected |
|--------|-------------|----------|
| `Platform.immutable` bloquea siempre + confirm explícito en el resto | Nunca automático en host inmutable (incl. Bazzite); confirm en el resto | ✓ |
| Detección específica Bazzite/KDE-SDDM | Bloqueo quirúrgico solo al caso documentado | |
| Solo confirm explícito, sin guard duro | Confiar en que el usuario lea el aviso, sin bloqueo automático | |

**User's choice:** Platform.immutable bloquea siempre + confirm explícito en el resto (Recomendado)
**Notes:** El roadmap pedía explícitamente ambas cosas ("an explicit confirm step **and** never automatic on immutable/atomic distros") — esta opción es la única que cubre las dos, reusando el primitivo `Platform.immutable` ya usado en `resolve.py` para el mismo tipo de riesgo.

---

## Dónde vive la acción de shell

| Option | Description | Selected |
|--------|-------------|----------|
| post_install action del ladder de oh-my-zsh, solo zsh | Dispatcher para la entrada existente en `POST_INSTALL_ACTIONS`/`model.py` | ✓ |
| Acción independiente invocable fuera de la instalación | Nueva superficie de UI para cambiar shell en cualquier momento | |
| Generalizar ya a cualquier shell futura | Dispatcher parametrizado desde el inicio | |

**User's choice:** post_install action del ladder de oh-my-zsh, solo zsh (Recomendado)
**Notes:** Es exactamente lo que el roadmap describe como scaffolding ya validado en el schema; no hay un segundo caso real de shell hoy en el registry para justificar generalizar.

---

## Claude's Discretion

- Wording exacto de la línea de resumen para tools bloqueadas por el gate (mientras reutilice la razón de `action_update_tool`).
- Forma exacta de la UI de confirmación del shell (modal vs `_ask_select`-style), siguiendo el patrón de `prompter.confirm(...)` ya usado en `run_wizard`.

## Deferred Ideas

None — discussion stayed within phase scope.
