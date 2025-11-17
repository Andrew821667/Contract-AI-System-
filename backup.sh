#!/bin/bash
# ==============================================
# Contract AI System - Backup Script
# ==============================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
BACKUP_DIR="/backup/contract-ai"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
COMPOSE_FILE="docker-compose.production.yml"
RETENTION_DAYS=30  # Keep backups for 30 days

# Load environment variables
if [ -f .env.production ]; then
    export $(cat .env.production | grep -v '^#' | xargs)
fi

# Functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Create backup directory
create_backup_dir() {
    mkdir -p "$BACKUP_DIR"
    print_success "Backup directory created: $BACKUP_DIR"
}

# Backup PostgreSQL database
backup_database() {
    print_info "Backing up PostgreSQL database..."

    DB_BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz"

    docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$DB_BACKUP_FILE"

    if [ -f "$DB_BACKUP_FILE" ]; then
        SIZE=$(du -h "$DB_BACKUP_FILE" | cut -f1)
        print_success "Database backed up: $DB_BACKUP_FILE ($SIZE)"
    else
        print_error "Database backup failed!"
        exit 1
    fi
}

# Backup uploaded files
backup_files() {
    print_info "Backing up uploaded files..."

    FILES_BACKUP="$BACKUP_DIR/files_backup_$TIMESTAMP.tar.gz"

    tar -czf "$FILES_BACKUP" \
        data/uploads \
        data/templates \
        data/reports \
        database \
        2>/dev/null || true

    if [ -f "$FILES_BACKUP" ]; then
        SIZE=$(du -h "$FILES_BACKUP" | cut -f1)
        print_success "Files backed up: $FILES_BACKUP ($SIZE)"
    else
        print_error "Files backup failed!"
        exit 1
    fi
}

# Backup ChromaDB vector store
backup_chroma() {
    print_info "Backing up ChromaDB..."

    CHROMA_BACKUP="$BACKUP_DIR/chroma_backup_$TIMESTAMP.tar.gz"

    docker run --rm \
        -v contract-ai-system-_chroma_data:/data \
        -v "$BACKUP_DIR":/backup \
        alpine \
        tar -czf "/backup/chroma_backup_$TIMESTAMP.tar.gz" -C / data \
        2>/dev/null || true

    if [ -f "$CHROMA_BACKUP" ]; then
        SIZE=$(du -h "$CHROMA_BACKUP" | cut -f1)
        print_success "ChromaDB backed up: $CHROMA_BACKUP ($SIZE)"
    else
        print_error "ChromaDB backup failed!"
    fi
}

# Backup configuration files
backup_config() {
    print_info "Backing up configuration files..."

    CONFIG_BACKUP="$BACKUP_DIR/config_backup_$TIMESTAMP.tar.gz"

    tar -czf "$CONFIG_BACKUP" \
        .env.production \
        nginx/ \
        docker-compose.production.yml \
        2>/dev/null || true

    if [ -f "$CONFIG_BACKUP" ]; then
        SIZE=$(du -h "$CONFIG_BACKUP" | cut -f1)
        print_success "Config backed up: $CONFIG_BACKUP ($SIZE)"
    else
        print_error "Config backup failed!"
    fi
}

# Clean old backups
cleanup_old_backups() {
    print_info "Cleaning up backups older than $RETENTION_DAYS days..."

    find "$BACKUP_DIR" -name "*.gz" -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR" -name "*.sql" -mtime +$RETENTION_DAYS -delete

    print_success "Old backups cleaned up"
}

# Create backup manifest
create_manifest() {
    MANIFEST="$BACKUP_DIR/manifest_$TIMESTAMP.txt"

    cat > "$MANIFEST" << EOF
Contract AI System - Backup Manifest
=====================================
Date: $(date)
Timestamp: $TIMESTAMP

Files:
------
$(ls -lh "$BACKUP_DIR"/*_$TIMESTAMP.*)

Checksums (MD5):
----------------
$(md5sum "$BACKUP_DIR"/*_$TIMESTAMP.* 2>/dev/null || echo "N/A")

Docker Containers:
------------------
$(docker-compose -f "$COMPOSE_FILE" ps)

System Info:
------------
Disk Usage: $(df -h / | tail -1)
Memory: $(free -h | grep Mem)
Swap: $(free -h | grep Swap)
EOF

    print_success "Manifest created: $MANIFEST"
}

# Restore from backup
restore_backup() {
    if [ -z "$1" ]; then
        print_error "Usage: $0 restore TIMESTAMP"
        print_info "Available backups:"
        ls -lh "$BACKUP_DIR"/db_backup_*.sql.gz | awk '{print $9}' | xargs -n1 basename
        exit 1
    fi

    RESTORE_TIMESTAMP=$1
    DB_FILE="$BACKUP_DIR/db_backup_$RESTORE_TIMESTAMP.sql.gz"
    FILES_FILE="$BACKUP_DIR/files_backup_$RESTORE_TIMESTAMP.tar.gz"

    if [ ! -f "$DB_FILE" ]; then
        print_error "Backup not found: $DB_FILE"
        exit 1
    fi

    print_info "Restoring from backup: $RESTORE_TIMESTAMP"

    # Stop services
    docker-compose -f "$COMPOSE_FILE" down

    # Restore database
    print_info "Restoring database..."
    docker-compose -f "$COMPOSE_FILE" up -d postgres
    sleep 5

    gunzip -c "$DB_FILE" | docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"

    # Restore files
    if [ -f "$FILES_FILE" ]; then
        print_info "Restoring files..."
        tar -xzf "$FILES_FILE"
    fi

    # Start services
    docker-compose -f "$COMPOSE_FILE" up -d

    print_success "Restore completed!"
}

# Main function
main() {
    case "${1:-backup}" in
        backup)
            echo "=========================================="
            echo "Contract AI System - Backup"
            echo "=========================================="
            create_backup_dir
            backup_database
            backup_files
            backup_chroma
            backup_config
            create_manifest
            cleanup_old_backups
            echo ""
            print_success "Backup completed successfully!"
            print_info "Backup location: $BACKUP_DIR"
            ;;
        restore)
            restore_backup "$2"
            ;;
        list)
            print_info "Available backups:"
            ls -lh "$BACKUP_DIR"/db_backup_*.sql.gz 2>/dev/null | awk '{print $5, $6, $7, $8, $9}'
            ;;
        *)
            echo "Usage: $0 {backup|restore TIMESTAMP|list}"
            exit 1
            ;;
    esac
}

# Run
main "$@"
