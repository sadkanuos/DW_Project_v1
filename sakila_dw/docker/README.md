# Docker Development Environment for sakila_dw

> **Purpose**: Containerized MySQL and PostgreSQL databases for local development and testing of the sakila_dw ETL pipeline.

---

## 🚀 Quick Start

### 1. Prerequisites

- [Docker](https://www.docker.com/) (Docker Desktop for Windows/macOS, Docker Engine for Linux)
- [Docker Compose](https://docs.docker.com/compose/) (included with Docker Desktop)
- Python 3.8+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### 2. Setup Environment

```bash
# Copy the example environment file
cp .env.example .env

# Customize the .env file with your preferred credentials
nano .env  # or use your preferred editor
```

### 3. Start Databases

```bash
# Start all services (PostgreSQL, MySQL, and Adminer)
docker-compose up -d

# Wait for databases to initialize (approx. 30-60 seconds)
docker-compose logs -f  # Monitor startup logs
```

### 4. Verify Databases

```bash
# Check PostgreSQL
psql -h localhost -p 5432 -U postgres -d sakila_dw

# Check MySQL
mysql -h localhost -P 3306 -u sakila -psakila sakila

# Or use Adminer web interface
# Open http://localhost:8080 in your browser
```

### 5. Run ETL Pipeline

```bash
# Install dependencies (if using uv)
uv sync

# Run the ETL pipeline
uv run python orchestrate.py
```

---

## 📊 Services

| Service | Port | Credentials | Purpose |
|---------|------|-------------|---------|
| PostgreSQL | 5432 | postgres/postgres | Data Warehouse (mart schema) |
| MySQL | 3306 | sakila/sakila | Source Database (sakila schema) |
| Adminer | 8080 | N/A | Database Management UI (optional) |

---

## 🏗️ Configuration

### Environment Variables

The `docker-compose.yml` file uses environment variables from `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PG_PORT` | 5432 | PostgreSQL port |
| `PG_USER` | postgres | PostgreSQL username |
| `PG_PASSWORD` | postgres | PostgreSQL password |
| `PG_DB` | sakila_dw | PostgreSQL database name |
| `MYSQL_PORT` | 3306 | MySQL port |
| `MYSQL_ROOT_PASSWORD` | mysqlroot | MySQL root password |
| `MYSQL_USER` | sakila | MySQL ETL user |
| `MYSQL_PASSWORD` | sakila | MySQL ETL password |
| `MYSQL_DB` | sakila | MySQL database name |

### Customizing Configuration

1. **Change Ports**: Modify the port mappings in `docker-compose.yml`
2. **Change Credentials**: Update the `.env` file
3. **Add Indexes**: Modify the initialization SQL files
4. **Add More Data**: Extend the initialization SQL files

---

## 📁 Files

```
docker/
├── docker-compose.yml      # Docker Compose configuration
├── init-postgres.sql      # PostgreSQL initialization script
├── init-mysql.sql         # MySQL initialization script
└── README.md              # This file
```

### Initialization Scripts

The initialization scripts (`init-postgres.sql` and `init-mysql.sql`) run automatically when the containers start for the first time. They:

1. **Create all required schemas** (etl, staging, mart for PostgreSQL)
2. **Create all required tables** with proper constraints
3. **Insert sample data** for testing
4. **Create users** with appropriate permissions
5. **Create indexes** for better performance

---

## 🔧 Common Commands

### Database Management

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Stop and remove volumes (reset databases)
docker-compose down -v

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs postgres
docker-compose logs mysql

# Execute command in PostgreSQL container
docker-compose exec postgres psql -U postgres -d sakila_dw

# Execute command in MySQL container
docker-compose exec mysql mysql -u root -p

# Restart services
docker-compose restart

# Rebuild containers (after changing Dockerfile or images)
docker-compose build
```

### Application Development

```bash
# Install Python dependencies (uv)
uv sync

# Run ETL pipeline
uv run python orchestrate.py

# Run tests
uv run pytest tests/

# Open Python shell with dependencies
uv run python

# Format code (if ruff is installed)
uv run ruff check .
uv run ruff format .
```

---

## 🐳 Adminer (Optional)

Adminer is a lightweight database management tool included in the Docker Compose configuration:

- **Access**: http://localhost:8080
- **To disable**: Remove the `adminer` service from `docker-compose.yml` or use `--profile tools` flag

### Starting without Adminer

```bash
# Start only databases (no Adminer)
docker-compose --profile base up -d

# Or modify docker-compose.yml to remove adminer service
```

---

## 🔒 Security Notes

### Default Credentials

For development convenience, the default credentials are:
- **PostgreSQL**: `postgres/postgres`
- **MySQL**: `sakila/sakila` (ETL user), `root/mysqlroot` (admin)

**⚠️ WARNING**: These are development credentials only. Do NOT use in production.

### Production Considerations

For production environments:
1. Use strong, random passwords
2. Create separate users with minimal privileges
3. Use SSL/TLS for database connections
4. Consider using a secrets management system
5. Do not expose database ports to the internet

---

## ❓ Troubleshooting

### "Port already in use" Error

```bash
# Find which process is using the port
lsof -i :5432  # For PostgreSQL
lsof -i :3306  # For MySQL

# Stop the conflicting process or change the port in .env
```

### Database Won't Start

```bash
# Check logs for errors
docker-compose logs postgres
docker-compose logs mysql

# Try resetting volumes
docker-compose down -v
docker-compose up -d
```

### Connection Refused

```bash
# Verify containers are running
docker-compose ps

# Check if databases are ready
docker-compose exec postgres pg_isready -U postgres
```

### Initialization Script Errors

```bash
# View the initialization logs
docker-compose logs postgres

# Manually run the initialization
cat docker/init-postgres.sql | docker-compose exec -T postgres psql -U postgres
```

---

## 🎯 Database Schema Reference

### PostgreSQL (Data Warehouse)

**Schemas:**
- `etl` - Audit tables (batch, load_log, dq_results)
- `staging` - Staging tables (customer, film, category, etc.)
- `mart` - Data mart (dimensions, facts, bridges)

**Tables:**
- `etl.batch` - Batch execution tracking
- `etl.load_log` - Step-level logging
- `etl.dq_results` - Data quality check results
- `staging.*` - Source data tables
- `mart.dim_*` - Dimension tables
- `mart.bridge_*` - Bridge tables
- `mart.fact_*` - Fact tables

### MySQL (Source Database)

**Database:** `sakila`

**Tables:**
- `actor`, `address`, `category`, `city`, `country`
- `customer`, `film`, `film_category`, `inventory`
- `language`, `payment`, `rental`, `staff`, `store`

---

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [MySQL Documentation](https://dev.mysql.com/doc/)
- [Adminer Documentation](https://www.adminer.org/)

---

## 💡 Tips

1. **Persist Data**: The Docker volumes (`postgres_data`, `mysql_data`) persist data between container restarts. To completely reset, use `docker-compose down -v`.

2. **Backup Data**: To backup your database data:
   ```bash
   docker-compose exec postgres pg_dump -U postgres sakila_dw > backup.sql
   docker-compose exec mysql mysqldump -u root -p sakila > backup-mysql.sql
   ```

3. **Restore Data**: To restore from backup:
   ```bash
   cat backup.sql | docker-compose exec -T postgres psql -U postgres sakila_dw
   cat backup-mysql.sql | docker-compose exec -T mysql mysql -u root -p sakila
   ```

4. **Multiple Instances**: To run multiple instances, create separate docker-compose files with different port mappings.

5. **Custom Images**: To use different database versions, modify the `image:` field in `docker-compose.yml`.

---

*Last Updated: 2026-10-03*  
*Version: 1.0*