<div align="center">
  <h1>PKU-DAIR Portal Backend</h1>

  <p>
    <a href="https://www.python.org/">
      <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+" />
    </a>
    <a href="https://fastapi.tiangolo.com/">
      <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
    </a>
    <a href="https://www.sqlite.org/">
      <img src="https://img.shields.io/badge/SQLite-Storage-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite" />
    </a>
    <a href="#license">
      <img src="https://img.shields.io/badge/License-MIT-2F80ED?style=flat-square" alt="MIT License" />
    </a>
  </p>

  <h4><i>Backend service for the PKU-DAIR team portal</i></h4>
</div>

---

## 1. Overview

PKU-DAIR Portal Backend provides the API service for the PKU-DAIR team portal. It manages users, members, teams, groups, education labels, awards, news, publications, and related uploaded assets.

The service is built with FastAPI and Tortoise ORM, using SQLite as the default database.

```text
Client / Admin UI
        |
        v
FastAPI Routers
        |
        v
Tortoise ORM + SQLite
        |
        +-- db/
        +-- member_cv/
        +-- news/
        +-- user/
        +-- backup/
```

---

## 2. Features

* User authentication and profile management
* Member CV and avatar storage
* News content and banner storage
* Team, group, major, education, destination, and award metadata APIs
* Publication record management
* SQLite schema generation through Tortoise ORM
* Automatic monthly database backups under `backup/db_YYYY_MM_DD`
* Docker Compose deployment with persistent host-mounted data

---

## 3. Project Structure

```text
.
├── app.py                         # FastAPI application entrypoint
├── api/
│   ├── controllers/               # API routers
│   └── models/                    # ORM models, auth helpers, backup logic
├── config/
│   └── app_config.json.sample     # Config template
├── db/                            # SQLite database and legacy JSON data
├── member_cv/                     # Member CV files and avatars
├── news/                          # News content and banner assets
├── user/                          # User avatar assets
├── backup/                        # Auto-generated database backups
├── docker-compose.yml
├── dockerfile
└── requirements.txt
```

---

## 4. Quick Start

### 4.1 Install Dependencies

```bash
pip install -r requirements.txt
```

### 4.2 Configure the App

Create the runtime config file:

```bash
cp config/app_config.json.sample api/app_config.json
```

Edit `api/app_config.json` and set your API key if authentication is required. If no API key is configured, the app can run without authentication.

### 4.3 Start the Server

```bash
uvicorn app:app --host=0.0.0.0 --port=8000 --reload
```

The backend will be available at:

```text
http://localhost:8000
```

Interactive API docs are available at:

```text
http://localhost:8000/docs
```

---

## 5. Docker Deployment

Build and start the service:

```bash
docker compose up -d --build
```

Restart the running service:

```bash
docker compose restart
```

The default Compose file mounts runtime data to the host so database files, uploaded assets, and backups survive container rebuilds:

```yml
volumes:
  - /root/docker/apps/pku_dair_be/db:/app/db
  - /root/docker/apps/pku_dair_be/member_cv:/app/member_cv
  - /root/docker/apps/pku_dair_be/news:/app/news
  - /root/docker/apps/pku_dair_be/user:/app/user
  - /root/docker/apps/pku_dair_be/backup:/app/backup
```

Change the host paths before deployment if your server uses a different data directory.

---

## 6. Data and Backups

Runtime data is intentionally kept outside Git:

* `db/` stores `db.sqlite3` and legacy JSON data files.
* `member_cv/` stores member CV files and avatars.
* `news/` stores news content and banner assets.
* `user/` stores user avatar assets.
* `backup/` stores automatic database backups.

The backend checks database backups on startup, then checks once per day while the service is running. When the latest backup is at least 30 days old, it creates a new folder named with the current date:

```text
backup/db_2026_04_18
```

SQLite backups are created through SQLite's backup API, which is safer than copying a live database file directly.

---

## 7. API Modules

The backend registers routers for the main portal resources:

* `user`
* `major`
* `group`
* `edu`
* `team`
* `towhere`
* `award`
* `member`
* `news`
* `pub`

After starting the service, visit `/docs` to inspect request and response schemas.

---

## 8. Maintenance Notes

* Keep `api/app_config.json` private and do not commit it.
* Keep mounted runtime directories available before starting Docker.
* Do not delete host-mounted data directories during deployment.
* Check `backup/` periodically and move important backups to long-term storage when needed.

---

## License

MIT License

Copyright (c) 2026 PKU-DAIR

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
