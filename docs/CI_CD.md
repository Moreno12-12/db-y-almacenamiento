# CI/CD (DataOps) con GitHub Actions

## 1. Contexto: por qué automatizar

Ya teníamos **Terraform** (infraestructura como código para MongoDB Atlas) y
**scripts de Python** (ETL, Data Lake, DW, benchmarks). El siguiente paso lógico
en DevOps/DataOps es **automatizar su ejecución** para que cada cambio se
valide solo, sin depender de que alguien recuerde correr los comandos.

**¿Qué es DataOps?** Aplicar prácticas de DevOps (integración continua,
entrega continua, automatización) al ámbito de los datos: toda la cadena
ETL + infraestructura + pruebas se valida automáticamente en cada cambio.

## 2. Qué se implementó

**Archivo:** `.github/workflows/deploy.yml` (GitHub Actions)

| Disparador | Acción |
|---|---|
| `git push` a `main` | Ejecuta el pipeline completo de validación |
| Manual (`workflow_dispatch`) | Permite además ejecutar `terraform apply` con un botón |

**Pipeline (2 jobs en paralelo):**

```
git push ──┬── Job 1: Pruebas Python
           │    ├─ Python 3.12
           │    ├─ pip install -r requirements.txt
           │    └─ pytest tests/  (compila 17 scripts + funciones puras)
           │
           └── Job 2: Infraestructura Terraform
                ├─ terraform fmt -check
                ├─ terraform init
                ├─ terraform validate
                └─ terraform plan   (apply SOLO manual con botón)
```

**Seguridad:**
- Nunca se commitean secretos: `.env`, `terraform.tfvars`, claves JSON y
  `*.tfstate` están en `.gitignore`.
- El `terraform plan` usa variables de entorno `TF_VAR_*` desde **GitHub
  Secrets** (`ATLAS_PUBLIC_KEY`, `ATLAS_PRIVATE_KEY`, `ATLAS_PROJECT_ID`,
  `ATLAS_DB_PASSWORD`); si aún no existen, usa placeholders para no romper el
  pipeline (el plan sigue validando sintaxis y estructura).
- El `terraform apply` **nunca corre automáticamente**: solo se dispara
  manualmente desde la pestaña Actions con la opción `apply=true` (control de
  cambios en infraestructura real).

**Pruebas (`tests/test_smoke.py`):**
1. Compilación de los 17 scripts Python del proyecto.
2. `convertir_objectids` (ObjectId → string recursivo, requiere Parquet).
3. Zonas del Data Lake dual (`local` / `s3://`).
4. `clasificar_llave` (PK/FK del catálogo de datos).
5. `tipo_estandarizado` (tipos BSON → tipos del diccionario).

## 3. Cómo ejecutarlo localmente

```powershell
pip install pytest
pytest tests/ -v              # pruebas
terraform -chdir=terraform fmt -check
terraform -chdir=terraform init
terraform -chdir=terraform validate
```

## 4. Cómo verlo en GitHub

1. Repo: `https://github.com/Moreno12-12/db-y-almacenamiento`
2. Pestaña **Actions** → push a `main` → run "CI/CD DataOps".
3. Cada run muestra los 2 jobs (pruebas + terraform) en verde.
4. Para desplegar: *Run workflow* → marcar `apply` → *Run workflow*.

## 5. Configurar secrets (opcional, para plan real de Atlas)

GitHub → repo → Settings → Secrets and variables → Actions → New repository secret:

| Nombre | Valor |
|---|---|
| `ATLAS_PUBLIC_KEY` | Public Key de Atlas (API Keys) |
| `ATLAS_PRIVATE_KEY` | Private Key de Atlas |
| `ATLAS_PROJECT_ID` | ID del proyecto Atlas |
| `ATLAS_DB_PASSWORD` | Contraseña del usuario de BD |

## 6. Texto para el informe

> **CI/CD (DataOps).** Se implementó un pipeline de integración y entrega
> continua con **GitHub Actions** (`.github/workflows/deploy.yml`) para
> garantizar la entrega continua y la validación automática de la
> infraestructura y el código de procesamiento. Cada `git push` al branch
> `main` ejecuta en paralelo: (1) las pruebas automatizadas del código Python
> (pytest: compilación de los 17 scripts y pruebas de funciones clave) y
> (2) la validación de la infraestructura como código con Terraform
> (`fmt`, `init`, `validate`, `plan`). El despliegue real (`terraform apply`)
> es un paso **manual y controlado** desde la interfaz de Actions, lo que
> aplica el principio de menor privilegio: nadie puede modificar la
> infraestructura sin una acción explícita. Esto constituye nuestra práctica
> de **DataOps**: datos + infraestructura + pruebas versionados y validados
> automáticamente en cada cambio.
