import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

commands = [
    # Fix git safe directory
    'git config --global --add safe.directory /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin',
    
    # Copy ui folder using sudo
    'sudo cp -r /tmp/acm2-temp/acm2/acm2/ui /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/',
    
    # Fix ownership
    'sudo chown -R bitnami:bitnami /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/ui',
    
    # Verify copy
    'ls -la /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/ui/',
    
    # Git status
    'cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin && git status',
    
    # Git add
    'cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin && git add ui/',
    
    # Git commit
    'cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin && git commit -m "Add React UI source from backend repo"',
    
    # Git push
    'cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin && git push origin main',
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
