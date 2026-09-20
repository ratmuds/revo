import os

# ok so like this file doesnt actually really work i think but whatever :)))))


# ok so like this file doesnt actually really work i think but whatever :)))))



# ok so like this file doesnt actually really work i think but whatever :)))))




# Define the file that will store your version number
VERSION_FILE = 'version.txt'

# Read the current version number or start at 1 if the file doesn't exist
if os.path.exists(VERSION_FILE):
    with open(VERSION_FILE, 'r') as f:
        version_num = int(f.read().strip())
else:
    version_num = 1

# We only want to increase the number when we are actually uploading to the board!
Import("env")
if "upload" in COMMAND_LINE_TARGETS:
    version_num += 1
    with open(VERSION_FILE, 'w') as f:
        f.write(str(version_num))
    print(f">>> SUCCESS: Incremented Firmware Version to {version_num} <<<")

# Pass the version number to your C++ code as a global macro definition
env.Append(CPPDEFINES=[
    ("FIRMWARE_VERSION", version_num)
])
