#!/bin/bash
# =============================================================================
# ACM2 BACKEND START SCRIPT (Linux)
# =============================================================================
# The ONE script to restart the ACM2 backend server.
#
# Usage:
#   ./start-backend.sh           - Normal restart (clears caches, keeps data)
#   ./start-backend.sh --purge   - DESTRUCTIVE: Deletes all user data
#
# The server runs via systemd. Logs: journalctl -u acm2 -f
#
# NOTE: Frontend (WordPress/Bitnami) is on 16.145.206.59
#       Restart frontend: ssh ubuntu@16.145.206.59 'sudo /opt/bitnami/ctlscript.sh restart apache'
# =============================================================================

set -e

# Configuration
ACM2_ROOT="/opt/acm2"
ACM2_APP="$ACM2_ROOT/acm2"
DATA_DIR="$ACM2_APP/data"
CERTS_DIR="$ACM2_ROOT/certs"
VENV_PYTHON="$ACM2_ROOT/venv/bin/python"
SSL_CERT="$CERTS_DIR/cloudflare.crt"
SSL_KEY="$CERTS_DIR/cloudflare.key"
ACM2_PORT=443

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
PURGE=false
if [[ "$1" == "--purge" ]]; then
    PURGE=true
fi

# Header
echo ""
if $PURGE; then
    echo -e "${RED}=============================================${NC}"
    echo -e "${RED}  ACM2 RESTART - PURGE MODE${NC}"
    echo -e "${RED}  WARNING: ALL USER DATA WILL BE DELETED!${NC}"
    echo -e "${RED}=============================================${NC}"
else
    echo -e "${CYAN}=============================================${NC}"
    echo -e "${CYAN}  ACM2 BACKEND RESTART${NC}"
    echo -e "${CYAN}=============================================${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# STEP 1: Stop existing server
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/5] Stopping ACM2 backend server...${NC}"

if systemctl is-active --quiet acm2; then
    sudo systemctl stop acm2
    sleep 2
    echo -e "${GREEN}       Stopped acm2 service${NC}"
else
    echo -e "       Service was not running"
fi

# -----------------------------------------------------------------------------
# STEP 2: Clear Python caches
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[2/5] Clearing Python caches...${NC}"

pycache_count=$(find "$ACM2_ROOT" -type d -name "__pycache__" 2>/dev/null | wc -l)
find "$ACM2_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$ACM2_ROOT" -name "*.pyc" -delete 2>/dev/null || true

echo -e "${GREEN}       Removed $pycache_count __pycache__ directories${NC}"

# -----------------------------------------------------------------------------
# STEP 3: Checkpoint SQLite databases (prevents corruption)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[3/5] Checkpointing SQLite databases...${NC}"

sqlite_count=0
if [ -d "$DATA_DIR" ]; then
    for db in "$DATA_DIR"/*.db; do
        if [ -f "$db" ]; then
            sqlite3 "$db" "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null || true
            ((sqlite_count++))
        fi
    done
fi

echo -e "${GREEN}       Checkpointed $sqlite_count databases${NC}"

# -----------------------------------------------------------------------------
# STEP 4: PURGE MODE - Delete all user data (if --purge flag)
# -----------------------------------------------------------------------------
if $PURGE; then
    echo -e "${RED}[4/5] PURGING ALL USER DATA...${NC}"
    
    # Delete user databases
    deleted_count=0
    for db in "$DATA_DIR"/user_*.db*; do
        if [ -f "$db" ]; then
            rm -f "$db"
            ((deleted_count++))
        fi
    done
    echo -e "${RED}       Deleted $deleted_count user database file(s)${NC}"
    
    # Delete legacy master.db if exists
    if [ -f "$DATA_DIR/master.db" ]; then
        rm -f "$DATA_DIR/master.db"*
        echo -e "${RED}       Deleted master.db (legacy)${NC}"
    fi
else
    echo -e "       [4/5] Keeping user data (use --purge to delete)"
fi

# -----------------------------------------------------------------------------
# STEP 5: Start server via systemd
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5/5] Starting ACM2 backend server...${NC}"

# Verify SSL certs exist
if [ ! -f "$SSL_CERT" ]; then
    echo -e "${RED}       ERROR: SSL cert not found: $SSL_CERT${NC}"
    exit 1
fi
if [ ! -f "$SSL_KEY" ]; then
    echo -e "${RED}       ERROR: SSL key not found: $SSL_KEY${NC}"
    exit 1
fi

sudo systemctl start acm2
sleep 3

# Verify server is running
if systemctl is-active --quiet acm2; then
    echo -e "${GREEN}       Server started on port $ACM2_PORT with SSL${NC}"
else
    echo -e "${YELLOW}       Server may still be starting...${NC}"
    echo -e "${YELLOW}       Check logs: sudo journalctl -u acm2 -f${NC}"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}  RESTART COMPLETE${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
echo -e "${CYAN}  Backend URL:  https://$(hostname -I | awk '{print $1}')${NC}"
echo -e "${CYAN}  Data dir:     $DATA_DIR${NC}"
echo ""
echo -e "  View logs:    sudo journalctl -u acm2 -f"
echo -e "  Stop server:  sudo systemctl stop acm2"
echo ""
echo -e "${YELLOW}  Frontend (WordPress/Bitnami) is on a SEPARATE server.${NC}"
echo -e "${YELLOW}  Restart frontend via SSH:${NC}"
echo -e "    ssh ubuntu@16.145.206.59 'sudo /opt/bitnami/ctlscript.sh restart apache'"
echo ""
