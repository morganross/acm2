import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

print("Restarting Apache...")
stdin, stdout, stderr = ssh.exec_command('sudo /opt/bitnami/ctlscript.sh restart apache', timeout=60)
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
print("Done!")
