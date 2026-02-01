import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

cmd = "sudo find /opt -name mysql -type f 2>/dev/null"
stdin, stdout, stderr = ssh.exec_command(cmd)
print("MySQL locations:")
print(stdout.read().decode())
ssh.close()
