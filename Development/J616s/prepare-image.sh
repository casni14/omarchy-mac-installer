#!/bin/bash
# Runs only inside the disposable J616s builder, against /build/image/*.img.
set -euo pipefail
[[ $(uname -m) == aarch64 && -f /build/image/root.img && -f /build/image/boot.img ]]
mkdir -p /mnt/top /mnt/root /tmp/j616s-gnupg
chmod 700 /tmp/j616s-gnupg
python3 - <<'PY'
import hashlib,json
from pathlib import Path
pins=json.loads(Path('/source/packages.json').read_text())
actual={p.name for p in Path('/build/aurora-packages').glob('*.pkg.tar.xz')}
if actual != set(pins):
    raise SystemExit('Aurora package inventory differs from the pinned snapshot')
for name,digest in {**pins,'aurora-alarm.asc':'61958de67d68a099bb73075da94b244223d811a80e65edd512403a147734236d'}.items():
    path=Path('/build/aurora-packages')/name
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        raise SystemExit('Aurora input differs: '+name)
PY
gpg --homedir /tmp/j616s-gnupg --batch --import /build/aurora-packages/aurora-alarm.asc
for package in /build/aurora-packages/*.pkg.tar.xz; do
  gpg --homedir /tmp/j616s-gnupg --batch --verify "$package.sig" "$package"
done
cleanup() {
  sync
  umount -R /mnt/root 2>/dev/null || true
  umount /mnt/top 2>/dev/null || true
}
trap cleanup EXIT
mount -o loop,subvolid=5 /build/image/root.img /mnt/top
mount --bind /mnt/top/@ /mnt/root
mount -o loop /build/image/boot.img /mnt/root/boot
[[ ! -L /build/esp.img ]]
truncate -s 524288000 /build/esp.img
mkfs.vfat -F 32 -i 4f4d5801 /build/esp.img
mount -o loop /build/esp.img /mnt/root/boot/efi
cp -r /build/image/esp/. /mnt/root/boot/efi/
for name in dev proc sys; do
  mount --rbind "/$name" "/mnt/root/$name"
  mount --make-rslave "/mnt/root/$name"
done
mount -t tmpfs tmpfs /mnt/root/run
# Reproduce the Apple platform and U-Boot EFI environment, as the upstream builder does.
mount -t tmpfs tmpfs /mnt/root/sys/firmware
mkdir -p /mnt/root/sys/firmware/devicetree/base /mnt/root/sys/firmware/efi/efivars
printf 'apple,j616s\0apple,t6040\0' > /mnt/root/sys/firmware/devicetree/base/compatible
mount --bind /build/aurora-packages /mnt/root/mnt
# The live J616s refresh uses the same package-owned tree as this image build.
cat > /mnt/root/etc/default/update-m1n1 <<'CONFIG'
# J616s developer image, Aurora Alpha 14 boot contract.
export LC_ALL=C
M1N1=/usr/lib/asahi-boot/m1n1.bin
U_BOOT=/usr/lib/asahi-boot/u-boot-nodtb.bin
DTBS=$(pacman -Qlq linux-aurora | grep '/t6040-j616s\.dtb$')
[ -n "$DTBS" ] && [ -f "$DTBS" ] || { echo 'Missing package-owned J616s device tree' >&2; exit 1; }
CONFIG
# Signatures are independently verified above against the pinned Aurora key.
# Use a transaction-local configuration, leaving the installed signature policy intact.
sed 's/^LocalFileSigLevel = .*/LocalFileSigLevel = Never/' /mnt/root/etc/pacman.conf > /mnt/root/tmp/j616s-pacman.conf
for package in m1n1-aurora omarchy-aurora-firmware; do
  if chroot /mnt/root pacman -Qq | grep -Fxq "$package"; then
    chroot /mnt/root pacman -Rdd --noconfirm "$package"
  fi
done
chroot /mnt/root /bin/bash -c 'pacman --config /tmp/j616s-pacman.conf -U --noconfirm /mnt/*.pkg.tar.xz'
chroot /mnt/root pacman -Dk
chroot /mnt/root /bin/bash -c 'set -e; update-m1n1 /boot/efi/m1n1/boot.bin; printf "%s\n" usr/lib/modules/*/vmlinuz | /usr/share/libalpm/scripts/mkinitcpio install; mkinitcpio -P'
[[ -s /mnt/root/boot/efi/EFI/Linux/omarchy_linux-aurora.efi ]]
[[ -s /mnt/root/boot/efi/EFI/BOOT/BOOTAA64.EFI ]]
# Keep the matching experimental platform until a tested upgrade is supplied.
# The rest of Omarchy retains its normal package source and updater.
sed -i '/^\[options\]/a IgnorePkg = aura m1n1 m1n1-aurora linux-aurora linux-aurora-headers uboot-aurora mesa-aurora vulkan-aurora' /mnt/root/etc/pacman.conf
mkdir -p /mnt/root/boot/efi/aurora
cp /mnt/root/usr/share/aura/stage1/aura-raw.bin /mnt/root/boot/efi/aurora/stage1.bin
cp /mnt/root/boot/efi/m1n1/boot.bin /mnt/root/boot/efi/m1n1/boot-j616s.bin
rm -rf /build/esp-complete
mkdir -p /build/esp-complete
cp -r /mnt/root/boot/efi/. /build/esp-complete/
chroot /mnt/root pacman -Q > /build/j616s-packages.txt
rm -f /mnt/root/tmp/j616s-pacman.conf
# The factory reset baseline must contain the same J616s platform and boot settings.
btrfs subvolume delete /mnt/top/@factory
btrfs subvolume snapshot /mnt/top/@ /mnt/top/@factory
rm -f /mnt/top/@factory/var/lib/omarchy/provisioning/pending
rm -rf /mnt/top/@factory/var/lib/omarchy/mac-first-boot /mnt/top/@factory/var/lib/omarchy/first-boot
btrfs property set -ts /mnt/top/@factory ro true
