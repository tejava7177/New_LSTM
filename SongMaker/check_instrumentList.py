from music21 import instrument
for inst in dir(instrument):
    if inst[0].isupper():
        print(inst)