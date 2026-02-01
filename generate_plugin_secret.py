import paramiko
import secrets

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Generate a plugin secret
plugin_secret = 'sk_plugin_' + secrets.token_hex(32)
print(f"Generated plugin secret: {plugin_secret}")

# Insert it into WordPress options
cmd = f"""
MYSQL=/opt/bitnami/mariadb/bin/mysql
DB_NAME=$(sudo grep DB_NAME /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_USER=$(sudo grep DB_USER /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_PASS=$(sudo grep DB_PASSWORD /bitnami/wordpress/wp-config.php | cut -d"'" -f4)

echo "Inserting plugin secret..."
$MYSQL -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "INSERT INTO wp_options (option_name, option_value, autoload) VALUES ('acm2_plugin_secret', '{plugin_secret}', 'yes') ON DUPLICATE KEY UPDATE option_value='{plugin_secret}';" 2>&1

echo ""
echo "Verifying..."
$MYSQL -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -N -e "SELECT option_value FROM wp_options WHERE option_name='acm2_plugin_secret';" 2>&1
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
ssh.close()

print(f"\n{'='*60}")
print(f"PLUGIN SECRET: {plugin_secret}")
print(f"{'='*60}")
print("\nAdd this to backend .env file:")
print(f"ACM2_PLUGIN_SECRET={plugin_secret}")
