import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Check database tables
cmd = """
DB_NAME=$(sudo grep DB_NAME /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_USER=$(sudo grep DB_USER /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_PASS=$(sudo grep DB_PASSWORD /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_HOST=$(sudo grep DB_HOST /bitnami/wordpress/wp-config.php | cut -d"'" -f4)

echo "DB: $DB_NAME @ $DB_HOST"
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema=DATABASE();" 2>/dev/null

echo ""
echo "=== wp_options related to plugins ==="
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SELECT option_name FROM wp_options WHERE option_name LIKE 'active%' OR option_name LIKE '%acm%';" 2>/dev/null
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)
ssh.close()
