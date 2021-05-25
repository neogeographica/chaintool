*** overview

This is a small example of using chaintool to create tools for accessing EC2 VMs -- particularly when you only know the VM names (not their IPs) off the top of your head. The commands and sequences here allow querying a VM's public/private IP, logging in to a VM via ssh, and securely transferring a file into a VM.

The purpose of this setup is to be a minimally-complex but not totally-uninteresting demonstration of:
- placeholder usage
- placeholders with defaults
- toggles

The above concepts should be illustrated just by using the commands and sequences below. If you dig into the implementation details a bit more by using "chaintool cmd print" and "chaintool seq print", you'll pick up more about the above topics as well as:
- composing sequences from commands
- using stdout from a command as part of a subsequent command

This is NOT meant to be a proof that using chaintool is the best way to accomplish these EC2-related tasks. (Although, if you're already familiar with chaintool, it's not a bad option.)


*** prerequisites

Using these tools does require that you have at least one EC2 VM that is network-accessible from your current computer.

Also, these tools require that the VM was set up with key-based ssh access, that you have the file containing the relevant private key, and that the VM's guest OS and its network policies support and allow ssh/scp access.

The client-side programs invoked are: aws, ssh, scp, and rsync. All are assumed to be on your PATH.

"aws" is the Amazon EC2 CLI. If you don't have it yet, you can get it with "python3 -m pip install awscli". Once you have it installed, you can set up your credentials (EC2 access key and secret key) by invoking "aws configure". This configuration process will also ask you for a default region and default output format; provide anything sensible for those items, but they won't matter for the purposes of these tools.

If you don't have "ssh", "scp", and/or "rsync", you'll need to get versions of those programs appropriate for your OS. On non-Windows platforms you should usually have most or all of these already.


*** setup

You can import the latest version of these commands/sequences from GitHub with:

  chaintool import https://raw.githubusercontent.com/neogeographica/chaintool/main/sample-imports/ec2tools

You will then want to use "chaintool vals" to set default values for the following placeholders:

  region : The EC2 region ID (e.g. us-east-1) for the VMs to access.
  ec2key : The absolute path to the file containing the private key for ssh access.

If the user associated with the ssh key is not named "ec2-user", you should also change the default for this placeholder:

  ec2user (currently ec2-user) : The user account that the private key authenticates to.

For example in my own case I would use the following command after import (the default "ec2-user" account name is fine with me):

  chaintool vals region=us-east-2 ec2key="/home/joel/AWS/key.pem"

If I had wanted to also indicate that my key was for the "joel" user account, I would have done this:

  chaintool vals region=us-east-2 ec2key="/home/joel/AWS/key.pem" ec2user=joel


*** running

Note that the examples below assume that you have chaintool shortcuts configured. If not, you need to prepend "chaintool cmd run" to any command invocation and "chaintool seq run" to any sequence invocation. It's good to have shortcuts!

If you have chaintool completions configured, tab-completion can be used to autocomplete the shortcut names as well as any placeholder arguments you want to specify.

The commands and sequences use the default region, private key, and VM user account you specified above. You can change those defaults at any time using another "vals" operation. Or, you can specify a different value for just the current run by setting it on the commandline, e.g. adding "region=us-west-1" as an argument to use the us-west-1 region for that invocation.

The ec2ip command can be used on its own if you just want to query the IP address of a VM with a given name:

  ec2ip vmname=my-vm-name

By default this will return the public IP (if any). If you'd rather query the private IP, use the toggle "+private":

  ec2ip +private vmname=my-vm-name

If a VM exists with that name (in your region) and has an IP of that type, the IP will be printed. Otherwise, "None" will be printed.

The ec2ip command is also part of the sequences below, so these same placeholders can affect those sequences. I.e. when running any of these sequences you must specify "vmname"; there's an optional "+private" toggle; and you can choose to specify "region", "ec2key", and/or "ec2user" if you don't want to use the defaults.

The ec2ssh sequence is used to log into the named VM (using ssh):

  ec2ssh vmname=my-vm-name

The ec2cp sequence is used to copy a file into the named VM (using scp):

  ec2cp vmname=my-vm-name source=my-file

An optional "dest" can be specified if you want the file to have a different name or go to a specific filepath inside the VM (instead of the home directory for the key user).

  ec2cp vmname=my-vm-name source=my-file dest=/desired/target/path/new-filename

(In the case of source or dest values, quoting the value may of course be necessary if the file or path includes whitespace or special characters.)

If a copy of a large file is interrupted and you want to try resuming from where it left off, use ec2p-resume instead of ec2cp. ec2cp will always overwrite any existing file at the destination, while if ec2p-resume sees an existing destination file it will see if that can be treated as a partial upload and resume (using rsync).

Note: The ec2ssh-ip, ec2cp-ip, and ec2cp-resume-ip commands behave like the above sequences, except that instead of specifying a value for the "vmname" placeholder on the commandline you must explicitly specify the IP as a value for the "ec2ip" placeholder. The "region" and "ec2key" placeholders and the "+private" toggle do not apply. These commands are used internally by the sequences above, as part of a look-up-the-IP-then-use-it process, but you can also run them directly if you like.


*** cleanup

The items created by this import can be deleted with:

  chaintool seq del ec2ssh ec2cp ec2cp-resume
  chaintool cmd del ec2ip ec2-save-stdout-as-ec2ip ec2ssh-ip ec2cp-ip ec2cp-resume-ip
