#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import random
import argparse
import subprocess
from subprocess import Popen, PIPE

# Generate random MAC address
def randomMAC():
    mac = [ 0x00, 0x16, 0x3e,
        random.randint(0x00, 0x7f),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff) ]
    return ':'.join(map(lambda x: "%02x" % x, mac))

# Create disk image
def createimg(machname, imgsize, imgpath=None):
    if os.path.isfile(imgpath):
        return imgpath
    elif os.path.isdir(imgpath):
        imgpath = imgpath + '/' + machname
    else:
        print 'Error! Provided path not found'
        sys.exit(1)
    cmd = "/usr/bin/qemu-img create -f raw {} {}K".format(imgpath, imgsize).split()
    run = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()
# Print error if is and exit
    if len(run[1]) > 0:
        print run[1]
        sys.exit(1)
    print run[0]
    return imgpath

# Prepare template to import with virsh
def preptempl(machname, mac, cpu=1, mem=524288, img=None):
    if not img:
        img = os.getcwd() + '/' + machname
    cmd = '/usr/bin/qemu-img info {}'.format(img).split()
    format = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()[0].split()[4]
    tmpl = '''
<domain type='kvm'>
  <name>{0}</name>
  <memory unit='KiB'>{1}</memory>
  <currentMemory unit='KiB'>{1}</currentMemory>
  <vcpu placement='static'>{2}</vcpu>
  <os>
    <type arch='x86_64' machine='pc-1.1'>hvm</type>
    <boot dev='hd'/>
  </os>
  <features>
    <acpi/>
    <apic/>
    <pae/>
  </features>
  <clock offset='utc'/>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>restart</on_crash>
  <devices>
    <emulator>/usr/bin/kvm</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='{3}' cache='none' io='native'/>
      <source file='{4}'/>
      <target dev='vda' bus='virtio'/>
      <address type='pci' domain='0x0000' bus='0x00' slot='0x05' function='0x0'/>
    </disk>
    <disk type='block' device='cdrom'>
      <driver name='qemu' type='raw'/>
      <target dev='hdc' bus='ide'/>
      <readonly/>
      <address type='drive' controller='0' bus='1' target='0' unit='0'/>
    </disk>
    <controller type='usb' index='0'>
      <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x2'/>
    </controller>
    <controller type='ide' index='0'>
      <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x1'/>
    </controller>
    <controller type='pci' index='0' model='pci-root'/>
    <interface type='network'>
      <mac address='{5}'/>
      <source network='default'/>
      <model type='virtio'/>
      <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
    </interface>
    <serial type='pty'>
      <target port='0'/>
    </serial>
    <console type='pty'>
      <target type='serial' port='0'/>
    </console>
    <input type='tablet' bus='usb'/>
    <input type='mouse' bus='ps2'/>
    <graphics type='vnc' port='-1' autoport='yes'/>
    <sound model='ich6'>
      <address type='pci' domain='0x0000' bus='0x00' slot='0x04' function='0x0'/>
    </sound>
    <video>
      <model type='cirrus' vram='9216' heads='1'/>
      <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x0'/>
    </video>
    <memballoon model='virtio'>
      <address type='pci' domain='0x0000' bus='0x00' slot='0x06' function='0x0'/>
    </memballoon>
  </devices>
</domain> '''.format(machname, mem, cpu, format, img, mac)
    tmpf = '/tmp/' + machname + str(random.randint(1, 1000)) + '.xml'
    f = open(tmpf, 'w')
    f.write(tmpl)
    f.close()
    print 'Temporary template written in', tmpf
    return tmpf

# Get IP address of running machine
def getip(mac):
    try:
        lease = open('/var/lib/libvirt/dnsmasq/default.leases', 'r')
    except:
        print "Can't open /var/lib/libvirt/dnsmasq/default.leases"
        sys.exit(1)
    t = 0
    ip = None
    print 'Waiting for machine\'s ip...'
    while t < 60:
        lease = open('/var/lib/libvirt/dnsmasq/default.leases', 'r')
        for i in lease.readlines():
            if mac in i:
                ip = i.split()[2]
                t = 60
                break
        time.sleep(1)
        lease.close()
        t += 1
    if not ip:
        return 'not found'
    return ip

# Here we parse all the commands
parser = argparse.ArgumentParser(prog='virtup.py')
parser.add_argument('-v', '--version', action='version', version='%(prog)s 0.1')
subparsers = parser.add_subparsers(dest='sub')
# Parent argparser to contain repeated arguments
parent = argparse.ArgumentParser(add_help=False)
parent.add_argument('-n', dest='name', type=str, required=True, 
                    help='virtual machine name')
parent.add_argument('-c', dest='cpus', type=int, default=1, 
                    help='amount of CPU cores, default is 1')
parent.add_argument('-m', dest='mem', metavar='RAM', type=str, default='512M', 
                    help='amount of memory, can be M or G, default is 512M')
box_add = subparsers.add_parser('add', parents=[parent], 
    description='Add virtual machine from image file', 
    help='Add virtual machine from image file')
box_add.add_argument('image', type=argparse.FileType('r'), help='image file location')
box_create = subparsers.add_parser('create', parents=[parent], 
    description='Create virtual machine from scratch', 
    help='Create virtual machine')
box_create.add_argument('-p', dest='image', type=str, default='/var/lib/libvirt/images', 
    help='path to directory where image will be stored, default is /var/lib/libvirt/images')
box_create.add_argument('-s', dest='size', type=str, default='8G', 
                    help='disk image size, can be M or G, default is 8G')
help_c = subparsers.add_parser('help')
help_c.add_argument('command', nargs="?", default=None)

def argcheck(arg):
    if arg[-1].lower() == 'm':
        return int(arg[:-1]) * 1024
    elif arg[-1].lower() == 'g':
        return int(arg[:-1]) * 1024 * 1024
    else:
        print 'Error! Format can be <int>M or <int>G'
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        parser.parse_args(['--help'])
    args = parser.parse_args()
# Help command emulation
    if args.sub == "help":
        if not args.command:
            parser.parse_args(['--help'])
        else:
            parser.parse_args([args.command, '--help'])
    mem = argcheck(args.mem)
    if args.sub == 'create':
        imgsize = argcheck(args.size)
    else:
        imgsize = argcheck('8G')
    mac = randomMAC()
    image = createimg(args.name, imgsize, os.path.abspath(args.image))
#    template = preptempl(args.name, mac, args.cpus, mem, image)
#    cmd = '/usr/bin/virsh define {}'.format(template).split()
#    run = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()
#    if len(run[1]) > 1:
#        print run[1]
#        sys.exit(1)
#    print run[0].rstrip()
#    cmd = '/usr/bin/virsh start {}'.format(args.name).split()
#    run = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()
#    print run[0].rstrip()
#    ip = getip(mac)
#    print 'You can connect to running machine at', ip
