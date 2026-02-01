import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Get the plugin secret and test user creation
cmd = """
MYSQL=/opt/bitnami/mariadb/bin/mysql
DB_NAME=$(sudo grep DB_NAME /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_USER=$(sudo grep DB_USER /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_PASS=$(sudo grep DB_PASSWORD /bitnami/wordpress/wp-config.php | cut -d"'" -f4)

PLUGIN_SECRET=$($MYSQL -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -N -e "SELECT option_value FROM wp_options WHERE option_name='acm2_plugin_secret';" 2>/dev/null)

echo "Plugin Secret: $PLUGIN_SECRET"
echo ""
echo "Testing user creation..."

curl -s -X POST http://54.71.183.56/api/v1/users \\
  -H "Content-Type: application/json" \\
  -H "X-ACM2-Plugin-Secret: $PLUGIN_SECRET" \\
  -d '{"username": "testuser3", "email": "test3@example.com", "wordpress_user_id": 3}'
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
ssh.close()
