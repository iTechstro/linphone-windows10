#!/usr/bin/env python

############################################################################
# nuget.py
# Copyright (C) 2016  Belledonne Communications, Grenoble France
#
############################################################################
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
############################################################################


import argparse
import glob
import os
import os.path
import shutil
import sys


platforms = ['ARM', 'x64', 'x86']


class PlatformListAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        if values:
            for value in values:
                if value not in platforms:
                    message = ("invalid platform: {0!r} (choose from {1})".format(value, ', '.join([repr(platform) for platform in platforms])))
                    raise argparse.ArgumentError(self, message)
            setattr(namespace, self.dest, values)


def handle_remove_read_only(func, path, exc):
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


def main(argv=None):
    if argv is None:
        argv = sys.argv
    argparser = argparse.ArgumentParser(
        description="Generate nuget package of Linphone SDK.")
    argparser.add_argument(
        '-s', '--sdk_dir', default="OUTPUT", help="The path where to find the built SDK", dest='sdk_dir')
    argparser.add_argument(
        '-t', '--target', default="Linphone", help="The target to package (the windows runtime whose metadata will be exported)", dest='target')
    argparser.add_argument(
        '-w', '--work_dir', default="WORK/nuget", help="The path where the work will be done to generate the nuget package", dest='work_dir')
    argparser.add_argument(
        'platform', nargs='*', action=PlatformListAction, default=['ARM', 'x64', 'x86'], help="The platform to build for (default is 'all'). Space separated architectures in list: {0}.".format(', '.join([repr(platform) for platform in platforms])))

    args, additional_args2 = argparser.parse_known_args()

    target_winmd = "Linphone.Native"
    if args.target == "LibLinphoneTester":
        target_winmd = "linphone_tester_runtime"
    elif args.target == "MS2Tester":
        target_winmd = "mediastreamer2_tester_runtime"
    elif args.target == "BelleSipTester":
        target_winmd = "belle_sip_tester_runtime"

    # Create work dir structure
    work_dir = os.path.abspath(args.work_dir)
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir, ignore_errors=False, onerror=handle_remove_read_only)
    os.makedirs(os.path.join(work_dir, 'lib', 'uap10.0'))
    for platform in args.platform:
        os.makedirs(os.path.join(work_dir, 'build', 'uap10.0', platform))
        os.makedirs(os.path.join(work_dir, 'runtimes', 'win10-' + platform.lower(), 'native'))

    # Copy SDK content to nuget package structure
    sdk_dir = os.path.abspath(args.sdk_dir)
    winmds_installed = False
    ignored_winmds = []
    for platform in args.platform:
    	platform_dir = 'win10-' + platform.lower()
        dlls = glob.glob(os.path.join(sdk_dir, platform_dir, 'bin', '*.dll'))
        dlls += glob.glob(os.path.join(sdk_dir, platform_dir, 'lib', '*.dll'))
        dlls += glob.glob(os.path.join(sdk_dir, platform_dir, 'lib', 'mediastreamer', 'plugins', '*.dll'))
        winmds = glob.glob(os.path.join(sdk_dir, platform_dir, 'bin', '*.winmd'))
        pdbs = glob.glob(os.path.join(sdk_dir, platform_dir, 'bin', '*.pdb'))
        pdbs += glob.glob(os.path.join(sdk_dir, platform_dir, 'lib', 'mediastreamer', 'plugins', '*.pdb'))

        if not winmds_installed:
            for winmd in winmds:
                basename = os.path.basename(winmd)
                basename_noext = os.path.splitext(basename)[0]
                if basename_noext == target_winmd:
                    shutil.copy(winmd, os.path.join(work_dir, 'lib', 'uap10.0'))
                else:
                    ignored_winmds += [basename_noext]
            winmds_installed = True
        for dll in dlls:
            basename = os.path.basename(dll)
            basename_noext = os.path.splitext(basename)[0]
            winmd = basename_noext + '.winmd'
            if os.path.exists(os.path.join(work_dir, 'lib', 'uap10.0', winmd)):
                shutil.copy(dll, os.path.join(work_dir, 'runtimes', platform_dir, 'native'))
            elif not basename_noext in ignored_winmds:
                shutil.copy(dll, os.path.join(work_dir, 'build', 'uap10.0', platform))
        for pdb in pdbs:
            shutil.copy(pdb, os.path.join(work_dir, 'build', 'uap10.0', platform))

    # Write targets file
    targets = """<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <!-- Note: This file will be injected into the target project -->
  <!-- Includes the native dll files as content to make sure that they are included in the app package -->
  <Target Name="CopyNativeLibraries" AfterTargets="ResolveAssemblyReferences">
    <ItemGroup>
      <Content Include="$(MSBuildThisFileDirectory)\$(Platform)\*.dll;$(MSBuildThisFileDirectory)\$(Platform)\*.pdb">
        <CopyToOutputDirectory>Always</CopyToOutputDirectory>
      </Content>
    </ItemGroup>
  </Target>
</Project>"""
    f = open(os.path.join(work_dir, 'build', 'uap10.0', args.target + 'SDK.targets'), 'w')
    f.write(targets)
    f.close()

    # Write nuspec file
    nuspec = """<?xml version="1.0"?>
<package >
  <metadata>
    <id>{target}SDK</id>
    <version>1.0.0</version>
    <authors>Belledonne Communications</authors>
    <owners>Belledonne Communications</owners>
    <licenseUrl>http://www.gnu.org/licenses/old-licenses/gpl-2.0.html</licenseUrl>
    <projectUrl>https://linphone.org/</projectUrl>
    <iconUrl>http://www.linphone.org/img/linphone-open-source-voip-projectX2.png</iconUrl>
    <requireLicenseAcceptance>false</requireLicenseAcceptance>
    <description>{target} SDK</description>
    <releaseNotes>Nothing new</releaseNotes>
    <copyright>Copyright 2016 Belledonne Communications</copyright>
    <tags>SIP</tags>
    <dependencies>
    </dependencies>
  </metadata>
</package>""".format(target=args.target)
    f = open(os.path.join(work_dir, args.target + 'SDK.nuspec'), 'w')
    f.write(nuspec)
    f.close()


if __name__ == "__main__":
    sys.exit(main())