import paramiko
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Command to add ACM2_BACKEND_URL to wp-config.php
cmd = """
# Check if already exists
if sudo grep -q 'ACM2_BACKEND_URL' /bitnami/wordpress/wp-config.php; then
    echo 'ACM2_BACKEND_URL already configured'
else
    # Add after <?php line
    sudo sed -i "2i define('ACM2_BACKEND_URL', 'http://54.71.183.56');" /bitnami/wordpress/wp-config.php
    echo 'Added ACM2_BACKEND_URL to wp-config.php'
fi

# Show the relevant line
echo '--- wp-config.php first 10 lines ---'
sudo head -10 /bitnami/wordpress/wp-config.php
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)
ssh.close()
