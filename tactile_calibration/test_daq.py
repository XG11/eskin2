import nidaqmx

print("Imported nidaqmx")

with nidaqmx.Task() as task:
    print("Task created")