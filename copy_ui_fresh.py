import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

commands = [
    # Remove existing ui folder and copy fresh
    'sudo rm -rf /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/ui',
    
    # Copy ui folder again from the cloned backend repo
    'sudo cp -r /tmp/acm2-temp/acm2/acm2/ui /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/',
    
    # Fix ownership of ui folder
    'sudo chown -R bitnami:bitnami /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/ui',
    
    # Verify copy
    'ls -la /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/ui/',
    
    # Use sudo to run git commands as bitnami
    'sudo -u bitnami git -C /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin add ui/',
    
    # Git status
    'sudo -u bitnami git -C /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin status',
    
    # Git commit
    'sudo -u bitnami git -C /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin commit -m "Add React UI source from backend repo"',
    
    # Git push
    'sudo -u bitnami git -C /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin push origin main',
]

for cmd in commands:
    print(f"\n{'='*60}")
    print(f"$ {cmd}")
    print('='*60)
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")

ssh.close()
print("\n\nDone!")
