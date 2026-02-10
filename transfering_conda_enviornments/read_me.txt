In the host machine:
conda env list
cd "DIRECTORY WHERE ENVIORNMENTS SHOULD BE EXPORTED"
conda activate gee-env
conda env export > gee-env.yml

Remove the last line of the exported yml file which looks like this:
prefix: C:\Users\arsha\.conda\envs\gee-env

Remove the build strings in the dependencies while keeping the version numbers
For example: 
Change: liblzma=5.8.1=h2466b09_0 → to → liblzma=5.8.1
------------------------------------------------------------------------------------------------
In the target machine:
conda env list
cd "DIRECTORY WHERE ENVIORNMENTS ARE LOCATED IN"
conda env create -f gee-env.yml

If version tug-of-war happens between the pip libraries, just delete the versoing of the libraiures involved, for example:
- boto3==1.40.41 
- botocore==1.40.18 
- aiobotocore==2.24.2 
→ to →
- boto3 
- botocore 
- aiobotocore

Then remove the failed env creation attempt:
conda env remove -n gee-env

And then try again:
conda env create -f gee-env.yml





