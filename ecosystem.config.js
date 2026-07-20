const path = require("path")

const REPO_ROOT = __dirname
const LOG_DIR = path.join(REPO_ROOT, "logs")

module.exports = {
  apps: [
    {
      name: "work-tracker-api",
      script: "python3",
      args: ["-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"],
      cwd: path.join(REPO_ROOT, "backend"),
      env: {
        PYTHONPATH: path.join(REPO_ROOT, "backend")
      },
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      error_file: path.join(LOG_DIR, "api-error.log"),
      out_file: path.join(LOG_DIR, "api-out.log"),
      log_file: path.join(LOG_DIR, "api-combined.log")
    },
    {
      name: "work-tracker-frontend",
      script: "npm",
      args: ["run", "dev"],
      cwd: path.join(REPO_ROOT, "frontend"),
      env: {
        VITE_API_BASE: "http://localhost:8001"
      },
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      error_file: path.join(LOG_DIR, "frontend-error.log"),
      out_file: path.join(LOG_DIR, "frontend-out.log"),
      log_file: path.join(LOG_DIR, "frontend-combined.log")
    }
  ]
}
