import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Check active plugins and acm2 options
cmd = """
DB_NAME=$(sudo grep DB_NAME /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_USER=$(sudo grep DB_USER /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_PASS=$(sudo grep DB_PASSWORD /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_HOST=$(sudo grep DB_HOST /bitnami/wordpress/wp-config.php | cut -d"'" -f4)

echo "=== Active Plugins ==="
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -N -e "SELECT option_value FROM wp_options WHERE option_name='active_plugins';" 2>/dev/null

echo ""
echo "=== All ACM2 Options ==="
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -N -e "SELECT option_name, option_value FROM wp_options WHERE option_name LIKE '%acm%';" 2>/dev/null

echo ""
echo "=== ACM2 API Keys Table ==="
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -N -e "SHOW TABLES LIKE '%acm%';" 2>/dev/null
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
ssh.close()
