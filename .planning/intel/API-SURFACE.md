# API Surface

> Generated from `.planning/intel/api-map.json`. Do not edit by hand.

## `CLI setup.py (make setup)`

- **method:** CLI
- **path:** uv run setup.py [ARGS]
- **params:** parsed by installer/cli.py parse_args -> Options
- **file:** setup.py
- **description:** Wizard: Textual catalog -> execute screen -> installs

## `make doctor`

- **method:** CLI
- **path:** make doctor
- **params:** 
- **file:** installer/app.py
- **description:** run_doctor read-only PATH audit

## `make fix`

- **method:** CLI
- **path:** make fix
- **params:** 
- **file:** installer/app.py
- **description:** configure_path wires ~/.myshellrc

## `make uninstall`

- **method:** CLI
- **path:** make uninstall
- **params:** 
- **file:** installer/app.py
- **description:** run_uninstall preview+confirm via uninstall.plan_uninstall

## `make guard/unguard`

- **method:** CLI
- **path:** make guard
- **params:** 
- **file:** installer/app.py
- **description:** run_guard pip/npm ban shims

## `make e2e`

- **method:** CLI
- **path:** scripts/container-e2e-verify.sh all
- **params:** 
- **file:** scripts/container-e2e-verify.sh
- **description:** real install/remove in disposable container
