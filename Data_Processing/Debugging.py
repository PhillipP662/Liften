import pickle

with open('../Data/Output/time_differences.pkl', 'rb') as f:
    time_differences = pickle.load(f)

# Example: access one location
for type in time_differences:
    print(type)

#print(time_differences['MACHINE_01'])  # Replace with actual code
