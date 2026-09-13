# Phase 15: Catalog Accuracy — Doctor Refresh, Version Parsing, Ownership Attribution, Tier Fixes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-13
**Phase:** 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at
**Areas discussed:** Mensaje del PATH check congelado, Estrategia de parsing de versión con prefijo, Cómo cablear dnf/apt/pacman al path vivo, Alcance de la corrección de tiers

---

## Mensaje del PATH check congelado

| Option | Description | Selected |
|--------|-------------|----------|
| Nota condicional solo tras aplicar el fix | Aparece solo cuando self.applied es True, junto al PATH item | ✓ |
| Nota fija siempre visible | Mismo texto siempre, aplicado o no | |

**User's choice:** Nota condicional solo tras aplicar el fix (Recomendado)
**Notes:** Coincide con la ventana de confusión real descrita en el roadmap — evitar ruido antes de que exista una discrepancia real entre "ya aplicado" y "el PATH vivo aún no lo refleja".

---

## Estrategia de parsing de versión con prefijo

| Option | Description | Selected |
|--------|-------------|----------|
| Split en '-'/espacio antes del segmento numérico | Genérico, sin lista de prefijos, sin riesgo de falsos positivos de un search libre | ✓ |
| Regex search libre en el texto completo | Buscar el patrón de versión como substring en cualquier posición | |
| Tabla de prefijos conocidos por tool en el registry | Cada tool declara explícitamente su formato | |

**User's choice:** Split en '-'/espacio antes del segmento numérico (Recomendado)
**Notes:** Cubre `jq-1.8.1` y casos similares sin registry-per-tool ni riesgo de ambigüedad de un search libre. Se auditará el registry por otros casos (D-04).

---

## Cómo cablear dnf/apt/pacman al path vivo

| Option | Description | Selected |
|--------|-------------|----------|
| Adaptar install_ownership.py mapeando 'verified'→'direct' | Reusa los probes ya escritos, traduce confidence al vocabulario MUTATION_GRADE | ✓ |
| Reimplementar probes nativos dentro de ownership.py | Un solo modelo de confidence, sin capa de traducción | |

**User's choice:** Adaptar install_ownership.py mapeando 'verified'→'direct' (Recomendado)
**Notes:** Evita duplicar lógica ya correcta y probada; cumple `.claude/architecture.md` regla 5.

**Sub-pregunta: probe faltante para rpm-ostree/just-layering (Bazzite)**

| Option | Description | Selected |
|--------|-------------|----------|
| Nuevo probe en install_ownership.py, mismo patrón que los existentes | rpm-ostree status --json, adaptado igual que los otros tres | ✓ |
| Diferirlo a una fase futura | Solo cablear dnf/apt/pacman esta fase | |

**User's choice:** Nuevo probe en install_ownership.py, mismo patrón que los existentes (Recomendado)
**Notes:** Se agrega en esta misma fase, no se difiere.

---

## Alcance de la corrección de tiers

| Option | Description | Selected |
|--------|-------------|----------|
| Los 6: ast-grep, puppeteer + evaluar y corregir mmdc/gitleaks/vale/drawio-cli también | Cierra el tema completo esta fase, incluye fix del comentario stale en ui_common.py | ✓ |
| Solo los 2 claros: ast-grep y puppeteer | Los 4 borderline quedan como deferred idea | |

**User's choice:** Los 6 (Recomendado)
**Notes:** Se presentó una tabla con tier propuesto para los 6, aplicando el criterio de `.claude/architecture.md`. El usuario confirmó la propuesta completa sin ajustes: ast-grep→ai, puppeteer→ai, mmdc/gitleaks/vale/drawio-cli permanecen user.

---

## Claude's Discretion

- Wording exacto de la nota condicional del PATH check (D-02).
- Qué tools ai-tier citar como ejemplo corregido en el comentario de ui_common.py (D-10).
- Comando/flags exactos del probe rpm-ostree (D-06) — detalle de implementación.

## Deferred Ideas

None — discussion stayed within phase scope. La revisión "borderline" de 4 tools se cerró en esta misma fase (D-09) en vez de diferirse.
