import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Get the plugin secret from WordPress database
cmd = """
# Get database credentials
DB_NAME=$(sudo grep DB_NAME /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_USER=$(sudo grep DB_USER /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_PASS=$(sudo grep DB_PASSWORD /bitnami/wordpress/wp-config.php | cut -d"'" -f4)
DB_HOST=$(sudo grep DB_HOST /bitnami/wordpress/wp-config.php | cut -d"'" -f4)

echo "Database: $DB_NAME"
echo "Querying for plugin secret..."

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -N -e "SELECT option_value FROM wp_options WHERE option_name='acm2_plugin_secret';" 2>/dev/null
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
output = stdout.read().decode()
print(output)
err = stderr.read().decode()
if err:
    print("STDERR:", err)
ssh.close()
