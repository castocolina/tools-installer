# AI Dev Tools Installer — Product Requirements Document (PRD)

> One-line goal: en una máquina nueva (macOS o Linux) ejecutar `curl -fsSL https://… | bash`
> y obtener un wizard TUI que deja seleccionar, por categoría y con barra espaciadora,
> todo el entorno de desarrollo AI — instalándolo sin sudo cuando sea posible y dejando el
> PATH correcto y deduplicado.

## Requirements Description

### Background

- **Business Problem**: aprovisionar un equipo de desarrollo nuevo (mac o varias distros Linux)
  es hoy un proceso manual, frágil y dependiente de Homebrew. El instalador actual de `uzkit`
  (`tools/`) ya resuelve el *qué* (registry declarativo de ~40 herramientas) pero tiene tres
  carencias: (1) la UI es un menú de texto donde escribes `1,3`, no una TUI interactiva con
  multi-select; (2) solo detecta `apt`/`pacman`/`brew`, faltan Fedora y distros inmutables;
  (3) no gestiona el PATH de forma activa (solo *imprime* sugerencias).
- **Target Users**: el propio autor (developer) montando entornos en macOS y Linux
  (Ubuntu, Pop!_OS, Manjaro, Fedora, Bazzite), incluyendo equipos corporativos donde no hay
  sudo a `/Applications` ni a paths de sistema. Secundariamente, cualquiera que clone el repo.
- **Value Proposition**: un único comando reproducible, independiente de Homebrew, que
  instala en userspace por defecto (`~/.local`, `~/Applications`), respeta sistemas atómicos
  e inmutables, y deja el shell con un PATH correcto y sin entradas duplicadas.

### Feature Overview

- **Core Features (v1 / MVP)**:
  1. **Bootstrap `curl | bash`**: detecta SO/arquitectura, asegura `uv` (vía el `.sh` oficial
     de Astral, *no* brew), obtiene el repo y lanza el wizard.
  2. **Wizard TUI interactivo**: navegación por categorías y multi-select con barra espaciadora
     (flechas para mover, espacio para marcar, enter para confirmar), construido sobre la base
     Python existente (`registry.toml` + estrategias).
  3. **PATH doctor + `~/.myshellrc`**: archivo único gestionado con todos los exports de PATH,
     idempotente y sin duplicados, cableado vía `source` en `.zshrc`/`.bashrc`; subcomando de
     auditoría que detecta bin_dirs faltantes, rotos o duplicados.
  4. **Soporte Fedora (dnf) + Bazzite (inmutable / rpm-ostree)** además de apt/pacman/brew.
  5. **Homebrew como paquete opcional** (brew-mac y brew-linux), instalable desde el propio
     wizard — nunca como dependencia previa.
- **Feature Boundaries (qué NO incluye v1)**:
  - No gestiona SSH ni configuración de git (el usuario ya lo cubre en otro proyecto).
  - No reescribe el motor en Go/Rust: se evoluciona el Python actual.
  - No incluire (todavía) los flujos de `register` Claude/Codex acoplados a uzkit ni
    `marketplace`/`launcher` AI más allá de lo que ya exista portado — se priorizan en v1.1.
  - No soporta Windows nativo (solo macOS + Linux; WSL queda fuera de v1).
- **User Scenarios**:
  - *Equipo nuevo*: `curl … | bash` → elegir categorías → marcar herramientas → instalar → PATH listo.
  - *Mantenimiento*: re-ejecutar para ver estado (current/missing/update) e instalar lo que falte.
  - *Corporativo sin sudo*: instala todo en `~/.local`/`~/Applications`, sin tocar rutas de sistema.
  - *Bazzite/inmutable*: instala en userspace y evita `rpm-ostree install` (que exige reboot).

### Detailed Requirements

- **Input/Output**:
  - *Input*: selección interactiva de categorías y tools (teclado); flags CLI no interactivos
    para automatización (`--all`, `--categories search,git`, `--doctor`, `--yes`).
  - *Output*: herramientas instaladas en sus `bin_dir`, `~/.myshellrc` actualizado, tabla de
    resumen (installed / still missing / failed) y reporte del PATH doctor.
- **User Interaction (flujo)**:
  1. Menú raíz: Everything · CLI tools · AI plugins · PATH doctor · Shell guards · Version sync.
  2. (CLI tools) lista de categorías con multi-select por barra espaciadora.
  3. Por cada categoría elegida, multi-select de tools (preseleccionadas las `missing`).
  4. Pre-flight audit (estado por tool) → confirmación → instalación ordenada por dependencias.
  5. PATH doctor corre al final (y como subcomando independiente).
- **Data Requirements**:
  - Fuente única de verdad: `registry.toml` (modelo `Tool` cargado con stdlib `tomllib`).
  - Nuevos campos por tool para la escalera de prioridad y ubicación (ver Design Decisions).
  - `~/.myshellrc`: bloque delimitado por marcadores (`# >>> tools-installer path >>>` …),
    una línea `export PATH` por bin_dir, sin duplicados.
- **Edge Cases**:
  - Distro inmutable detectada → saltar paso "nativo" de la escalera salvo override explícito.
  - `npm`/`pip` baneados (shims existentes) → node vía volta/pnpm, python vía uv.
  - `~/.myshellrc` ya existe con contenido del usuario → solo se toca el bloque marcado.
  - Un `.sh` oficial que falla → fallback automático al siguiente nivel de la escalera.
  - Sin red / rate-limit de GitHub → degradar con warning, no abortar todo el run.
  - macOS sin Command Line Tools / Linux sin `curl` → bootstrap lo detecta y guía.

## Design Decisions

### Technical Approach

- **Architecture Choice**: **evolucionar el instalador Python de uzkit hacia un repo
  standalone `tools-installer`**. Se conserva la arquitectura declarativa (registry +
  estrategias por `kind` + escape hatch `custom`) y se sustituye únicamente la capa de UI.
  Razón: el registry de ~40 tools y la lógica de detección/instalación están maduros; el
  coste de reescribir en Go/Rust no se justifica para un MVP cuyo cuello de botella es la UX,
  no el runtime. El bootstrap `uv` ya resuelve el "no hay Python en bare metal".
- **TUI library**: **`questionary`** (sobre `prompt_toolkit`) para el multi-select con barra
  espaciadora (`questionary.checkbox`), declarada como dependencia inline del script para `uv`.
  Es el match exacto del patrón categoría→checkbox (estilo `sv`/marketplace), más ligera que
  Textual y sin estado de app persistente. `rich` se mantiene para tablas y estado.
  *Alternativa considerada*: Textual (full TUI app) — descartada por sobre-ingeniería para v1.
- **Key Components**:
  - `install.sh` — bootstrap `curl|bash`: detecta SO/arch, asegura `uv` vía `https://astral.sh/uv/install.sh`,
    obtiene el repo (git clone o tarball de release), `exec uv run setup.py`.
  - `setup.py` — entrypoint del wizard (inline deps: `rich`, `questionary`).
  - `installer/model.py` — modelo `Tool` + loader `tomllib` (extiende campos de prioridad/ubicación).
  - `installer/registry.toml` — fuente de verdad declarativa (portada desde uzkit + nuevos campos).
  - `installer/strategies.py` — una estrategia por `kind`, ahora gobernadas por la **escalera de prioridad**.
  - `installer/platform.py` — detección de SO/arch extendida (debian/arch/fedora/macos + inmutable).
  - `installer/paths.py` — gestión de PATH (existente) + **PATH doctor** (nuevo: audita y escribe `~/.myshellrc`).
  - `installer/ui.py` — capa TUI (`questionary`) con navegación por categorías y multi-select.
- **Escalera de prioridad de instalación** (default global, override por tool en el registry):
  1. **`.sh` oficial del creador** si resuelve de verdad (uv, volta, opencode, etc.).
  2. **tar.gz / github-release** desempaquetado en `~/.local` (sin sudo) + symlink en `~/.local/bin`.
  3. **gestor nativo** de la distro: `dnf` (Fedora), `apt` (Debian/Ubuntu/Pop), `pacman` (Manjaro/Arch),
     `rpm-ostree` (solo si no-inmutable o con override).
  4. **Homebrew** como último recurso (mac y linux).
  En distros **inmutables** el nivel 3 se omite por defecto (se prefiere userspace o brew-linux).
- **Política de ubicaciones**:
  - CLIs/binarios → `~/.local/bin` (en PATH vía `~/.myshellrc`).
  - Apps desempaquetadas Linux → `~/.local/opt/<app>` + symlink del binario en `~/.local/bin`.
  - GUI macOS → `~/Applications` (nunca `/Applications`, evita sudo en equipos corporativos) + symlink CLI en `~/.local/bin`.
  - Se evita flatpak/appimage salvo que sea la única vía declarada para ese tool.
- **PATH doctor (`~/.myshellrc`)**:
  - Recolecta todos los `bin_dir` declarados + `~/.local/bin` y los escribe como `export PATH`
    dentro de un bloque marcado en `~/.myshellrc`, **sin entradas duplicadas**.
  - Asegura `source ~/.myshellrc` en `~/.zshrc` (si existe) y `~/.bashrc`, idempotente
    (reutiliza el patrón marker-delimited de `shell.py`, nunca duplica el `source`).
  - Subcomando `doctor`: escanea el PATH actual y los rc, reporta bin_dirs faltantes, rotos
    (dir inexistente) o duplicados, y ofrece arreglarlos.
- **Data Storage**: sin base de datos. Estado derivado en vivo de `which`/`--version` y de los
  ficheros de estado JSON que algunos launchers escriben (patrón `[tool.state]` ya existente).
- **Interface Design**: TUI interactiva + flags CLI no interactivos para CI/scripting.

### Constraints

- **Performance**: el wizard debe abrir en < 2 s tras el bootstrap; las llamadas de red
  (versión latest en GitHub/crates) con timeout corto (≤ 10 s) y degradación suave.
  Evitar el "brew tarda y se actualiza solo sin progreso" — no se dispara `brew update` salvo necesidad.
- **Compatibility**: Python ≥ 3.11 (provisto por `uv`); macOS (Apple Silicon + Intel) y
  Linux x86_64/aarch64; distros: Ubuntu, Pop!_OS, Debian, Manjaro/Arch, Fedora, Bazzite.
- **Security**: `curl|bash` sirve binarios/instaladores oficiales por HTTPS; preferencia por
  instaladores firmados/oficiales; sin sudo salvo el nivel "nativo" de la escalera, y avisando.
- **Scalability**: añadir un tool nuevo = una entrada en `registry.toml`; añadir una distro =
  una rama en `platform.py` + estrategia. La escalera de prioridad mantiene el coste por-distro acotado.

### Risk Assessment

- **Technical Risks**:
  - *Detección de inmutables poco fiable* (Bazzite/Silverblue) → mitigación: detectar
    `rpm-ostree` + `/run/ostree-booted`, y permitir override manual.
  - *`questionary` sobre terminales raras / no-TTY* → fallback a modo no interactivo (flags).
  - *Symlinks rotos al actualizar apps en `~/.local/opt`* → el doctor los detecta y re-enlaza.
- **Dependency Risks**:
  - *Astral cambia la URL del instalador de `uv`* → bootstrap con fallback (brew o pipx) y mensaje claro.
  - *Rate-limit de la API de GitHub* para versiones latest → cachear y degradar con warning.
- **Schedule Risks**: portar el registry + 40 tools y validar en 5 distros es lo más largo;
  mitigación: MVP cubre la ruta feliz por distro y deja la cola larga (`custom`) incremental.

## Acceptance Criteria

### Functional Acceptance

- [ ] `curl -fsSL <url>/install.sh | bash` en mac/Linux limpio detecta SO/arch, instala `uv`
      (sin brew) y abre el wizard sin pasos manuales.
- [ ] El wizard permite elegir categorías y, dentro de ellas, marcar/desmarcar tools con
      barra espaciadora (flechas + espacio + enter).
- [ ] La instalación respeta la escalera `.sh oficial → tar.gz ~/.local → nativo → brew`,
      con override por tool desde `registry.toml`.
- [ ] En macOS las GUI van a `~/Applications` y los CLIs a `~/.local/bin` (cero `/Applications`, cero sudo innecesario).
- [ ] El PATH doctor crea/actualiza `~/.myshellrc` con todos los exports necesarios **sin duplicados**
      y asegura `source ~/.myshellrc` en `.zshrc` (si existe) y `.bashrc`, idempotente.
- [ ] El subcomando `doctor` reporta bin_dirs faltantes/rotos/duplicados y los arregla.
- [ ] Fedora instala vía `dnf`; Bazzite/inmutable evita `rpm-ostree install` por defecto y usa userspace/brew-linux.
- [ ] Homebrew aparece como tool opcional instalable (brew-mac y brew-linux), no como prerequisito.
- [ ] Re-ejecutar es idempotente: lo ya instalado se marca `current` y no se reinstala.

### Quality Standards

- [ ] Code Quality: módulos enfocados (UI / modelo / estrategias / plataforma / paths separados),
      siguiendo el estilo del registry declarativo actual.
- [ ] Test Coverage: tests unitarios de (a) parsing de registry, (b) resolución de la escalera de
      prioridad, (c) idempotencia de `~/.myshellrc` (sin duplicados), (d) detección de SO/inmutable (mockeada).
- [ ] Performance: wizard abre < 2 s; llamadas de red con timeout ≤ 10 s y degradación suave.
- [ ] Security Review: revisión del `install.sh` (HTTPS, sin `eval` de contenido arbitrario, fallbacks).

### User Acceptance

- [ ] User Experience: la TUI se siente como `sv`/claude-marketplace (navegación fluida, espacio = toggle).
- [ ] Documentation: `README.md` con el one-liner `curl|bash`, matriz de distros soportadas y la
      política de ubicaciones/escalera.
- [ ] Validado manualmente en al menos: macOS + una distro `apt` + una `dnf`/inmutable.

## Execution Phases

### Phase 1: Preparation
**Goal**: Esqueleto del repo standalone y portado del núcleo declarativo.
- [ ] Inicializar estructura `tools-installer/` (`setup.py`, `installer/`, `install.sh`, `tests/`, `docs/`).
- [ ] Portar `model.py`, `registry.toml`, `engine.py`, `strategies.py`, `shell.py` desde uzkit, desacoplando lo específico de uzkit (register Claude/Codex queda fuera de v1).
- [ ] Definir los nuevos campos del modelo `Tool` para la escalera de prioridad y ubicación.
- **Deliverables**: repo que carga el registry y corre el menú-texto actual end-to-end.
- **Time**: ~1–2 días.

### Phase 2: Core Development
**Goal**: TUI interactiva + escalera de prioridad + PATH doctor.
- [ ] Implementar la capa UI con `questionary` (categorías + multi-select por barra espaciadora).
- [ ] Implementar la escalera de prioridad en `strategies.py` (default global + override por tool).
- [ ] Implementar el PATH doctor: escritura idempotente de `~/.myshellrc` + cableado `source` + dedup.
- [ ] Implementar el subcomando `doctor` de auditoría (faltantes/rotos/duplicados).
- **Deliverables**: wizard interactivo funcional con instalación y PATH gestionado.
- **Time**: ~3–4 días.

### Phase 3: Integration & Testing
**Goal**: Cobertura multi-distro y bootstrap.
- [ ] `platform.py`: detección extendida (debian/arch/fedora/macos + inmutable rpm-ostree).
- [ ] `install.sh`: bootstrap `curl|bash` (detect SO/arch → ensure uv → fetch repo → run wizard).
- [ ] Homebrew como tool opcional (brew-mac/brew-linux) en el registry.
- [ ] Tests unitarios (registry, escalera, idempotencia myshellrc, detección mockeada).
- [ ] Validación manual en macOS + apt + dnf/inmutable.
- **Deliverables**: instalable de punta a punta en las distros objetivo.
- **Time**: ~3–4 días.

### Phase 4: Deployment
**Goal**: Publicación y documentación.
- [ ] `README.md` (one-liner, matriz de distros, política de ubicaciones/escalera).
- [ ] Publicar el repo y la URL estable del `install.sh` (raw o GitHub Release).
- [ ] Checklist de smoke test post-publicación (`curl|bash` desde cero en una VM/contenedor limpio).
- **Deliverables**: `curl -fsSL <url> | bash` operativo y documentado.
- **Time**: ~1 día.

---

**Document Version**: 1.0
**Created**: 2026-06-08
**Clarification Rounds**: 2
**Quality Score**: 93/100
