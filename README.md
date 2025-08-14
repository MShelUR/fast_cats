# FastCATS
```
Create, read, and remove 
accounts on CATS.
What CATS does, FastCATS does better!
                -----
     (\\___/)  -----
    (= *.* =)    -----
                ----
```
## Usage
```
fastcats [-h] [-g GROUP] [-i INPUT] [-r] [--do-it]
  -h, --help            show this help message and exit
  -g GROUP, --group GROUP
                        Name of group to add the users to. Defaults to HPC (for spydur access)
  -i INPUT, --input INPUT
                        Input file name with netids, or the one netid to be added.
  -r, --remove          Remove the provided netids from the group.
  --do-it               Adding this switch will execute the commands as the program runs rather than print what actions will be taken.
```