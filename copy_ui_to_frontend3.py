import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

commands = [
    # Fix .git folder ownership
    'sudo chown -R bitnami:bitnami /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/.git',
    
    # Git add ui/
    'cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin && git add ui/',
    
    # Git status to confirm
    'cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin && git status',
    
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
