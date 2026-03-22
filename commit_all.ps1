Set-Location "c:\Users\Hp\Downloads\Voice Agent"

git add app/main.py
git commit -m "refactor: update main entrypoint"

git add app/static/index.html
git commit -m "feat: design index.html dashboard"

git add app/static/script.js
git commit -m "feat: handle client logic in script.js"

git add app/static/style.css
git commit -m "style: design clean layouts and transitions"

git add data/settings.json
git commit -m "config: apply general parameters structure"

git add app/agent.py
git commit -m "feat: migrate agent handler to root"

git add app/config.py
git commit -m "feat: include static app config"

git add app/database.py
git commit -m "feat: integrate flat database context"

git add app/rag.py
git commit -m "feat: include simple rag functionality"

git add app/settings.py
git commit -m "feat: update server config context layer"

git add app/whisper_client.py
git commit -m "feat: flat whisper client module"

git add -A AGENT.md CHANGELOG.md DEPENDENCIES.md
git commit -m "chore: cleanup unnecessary markdown files"

git add -A app/core app/db app/routers app/services
git commit -m "clean: remove old nested folder structure"

git add -A knowledge/soul_imaging_appointments.md knowledge/soul_imaging_faq.md knowledge/soul_imaging_overview.md knowledge/soul_imaging_services.md
git commit -m "docs: deprecate old knowledge models"

git add .
git commit -m "feat: add residual and docs files to static workspace"
