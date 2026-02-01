import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Use localhost without port specification
cmd = """
MYSQL=/opt/bitnami/mariadb/bin/mysql
DB_NAME=$(sudo grep DB_NAME /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_USER=$(sudo grep DB_USER /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_PASS=$(sudo grep DB_PASSWORD /bitnami/wordpress/wp-config.php | cut -d"'" -f4)

echo "Database: $DB_NAME, User: $DB_USER"

echo ""
echo "=== Active Plugins ==="
$MYSQL -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -N -e "SELECT option_value FROM wp_options WHERE option_name='active_plugins';" 2>&1

echo ""
echo "=== ACM2 Plugin Secret ==="
$MYSQL -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -N -e "SELECT option_value FROM wp_options WHERE option_name='acm2_plugin_secret';" 2>&1

echo ""
echo "=== ACM2 API Keys Table Exists? ==="
$MYSQL -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -N -e "SHOW TABLES LIKE 'wp_acm2_api_keys';" 2>&1
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
ssh.close()
