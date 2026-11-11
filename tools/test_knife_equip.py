#!/usr/bin/env python3
"""Source-bound knife intent controls; no game, GPU, account or asset access.

Executes the scalar production QC helper bodies as C with only builtin seams
stubbed. This is not a QC VM/transport or visual acceptance test.
"""
import argparse
from pathlib import Path
import os
import re
import subprocess


def body(source, name):
    match = re.search(r"void\(([^)]*)\) " + name + r" =\n\{", source)
    assert match, name
    end = source.index("\n};", match.end())
    args = match.group(1) or "void"
    code = f"static void {name}({args})\n{{" + source[match.end():end] + "\n}\n"
    code = code.replace("local float ", "float ").replace("fopen(", "qc_fopen(").replace("fclose(", "qc_fclose(")
    return re.sub(r"\b(\d+)i\b", r"\1", code)  # QC explicit integer literals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--compiler", default="C:/msys64/ucrt64/bin/gcc.exe")
    args = parser.parse_args()
    assert any((p / "OWNER.md").is_file() for p in args.work_root.parents)
    args.work_root.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    wp = (root / "src/client/cl_weapon.qc").read_text()
    vm = (root / "src/client/cl_viewmodel.qc").read_text()
    ui = (root / "src/client/cl_weaponui.qc").read_text()
    # Source wiring controls: only a successfully applied account row migrates;
    # the restore pump follows publication and the ACK precedes arming it.
    assert 'registercvar("cl_knife_equipped", "-1", CVAR_ARCHIVE)' in wp
    assert vm.index("VM_ApplyOwn(data);") < vm.index("saved_enabled = (revision > 0 && VM_Get(data, VM_ENABLED));")
    assert 'saved_enabled = FALSE;\n\t\tcurrent = VM_OwnSetup();' in vm
    assert vm.index('localcmd(sprintf("cmd vm_profile ack') < vm.index('WP_AccountKnifeReady(saved_enabled);')
    assert 'VM_PollOwn();\n\tWP_RestoreKnife();' in vm
    assert 'if (!strcmp(cmd, "drop")) { WP_Drop(); return TRUE; }' in wp
    assert '"Drop", tsz, FALSE)) WP_Drop();' in ui
    assert 'KCAT_ApplyChoice(kind);\n\tWP_EquipKnife();' in wp
    assert 'cvar_set("cl_knife_finish", ftos(i));\n\t\t\tWP_EquipKnife();' in ui
    assert 'WP_CancelKnifeChoice();\n\tif (w == FS_WEAPON_KNIFE)' in wp
    assert 'WP_CompleteKnifeChoice(stof(argv(1)), stoi(argv(2)));' in wp
    assert wp.count('knife_mount_done %g %i') == 3
    assert 'WP_MountKnifeContent(KCAT_Knife())' not in wp
    assert 'wp_modelmissing = TRUE;\n\t\t\t\tWP_MountKnifeContent(-1);' in wp
    assert 'wp_ready = FALSE;\n\t\twp_modelmissing = FALSE;' in wp
    assert 'WP_RetryMountedKnife();\n\t\t\tf = fopen(' in wp
    frame_condition = 'w != wp_weapon || strcmp(mdl, wp_model)'
    assert 'if (' + frame_condition + ')' in wp
    prefix = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define FALSE 0
#define TRUE 1
#define STAT_HEALTH 0
#define STAT_VM_WEAPON 1
#define FS_WEAPON_KNIFE 1
#define FILE_READ 0
static float intent, wp_restoreknife, wp_restoreat, time, mine, health, weapon, wp_explicitchoice;
static int equips, drops, wp_choiceepoch, completed, guns;
static float wp_modelmissing, wp_ready, wp_weapon, mirrored;
static int available, probes, closed, freed, mounts, loads;
static const char *wp_model="", *current_model="models/knife.mdl";
static float VM_Weapon(void) { return weapon; }
static float VM_IsMirroring(void) { return mirrored; }
static const char *WP_Model(float w) { assert(w==FS_WEAPON_KNIFE); return current_model; }
static float qc_fopen(const char *path, int mode) { assert(!strcmp(path,current_model) && mode==FILE_READ); probes++; return available?1:-1; }
static void qc_fclose(float file) { assert(file==1); closed++; }
static void strunzone(const char *path) { assert(!strcmp(path,current_model)); freed++; }
static const char *capability="1";
static const char *serverkey(const char *name) { assert(!strcmp(name,"*vmsetup")); return capability; }
static float cvar(const char *name) { assert(!strcmp(name,"cl_knife_equipped")); return intent; }
static void cvar_set(const char *name,const char *value) { assert(!strcmp(name,"cl_knife_equipped")); intent=(float)atof(value); }
static float LT_StatsAreMine(void) { return mine; }
static float getstatf(int stat) { return stat==STAT_HEALTH?health:weapon; }
static void localcmd(const char *command) {
 if (!strcmp(command,"cmd weapon knife\n")) equips++;
 else if (!strcmp(command,"cmd weapon_drop\n")) drops++;
 else if (!strcmp(command,"cmd weapon 4\n")) guns++;
 else assert(0);
}
static void map_epoch(void) { wp_restoreknife=wp_restoreat=time=weapon=wp_explicitchoice=0; wp_choiceepoch=0; mine=1; health=100; }
static void WP_ChooseKnifeReady(float kind);
'''
    helpers = "".join(body(wp, name) for name in ("WP_CancelKnifeChoice", "WP_EquipKnife", "WP_AccountKnifeReady", "WP_Drop", "WP_RestoreKnife", "WP_CompleteKnifeChoice", "WP_RetryMountedKnife"))
    # The ordinary frame's cache comparator is copied from production. The
    # surrounding asset/model work is a counted seam, not full WP_Frame execution.
    helpers += '''
static void ordinary_frame(void) {
 float w=weapon; const char *mdl=current_model;
 if (''' + frame_condition + ''') {
  wp_weapon=w; wp_ready=0; wp_modelmissing=0; wp_model=mdl;
  if (qc_fopen(wp_model,FILE_READ)<0) { wp_modelmissing=1; mounts++; return; }
  qc_fclose(1); loads++; wp_ready=1;
 }
}
''' 
    tests = r'''
// Model/asset probing is stubbed as successful; the production completion
// gate must reject stale epochs BEFORE entering this downstream seam.
static void WP_ChooseKnifeReady(float kind) { assert(kind==0); completed++; WP_EquipKnife(); localcmd("cmd weapon knife\n"); }
int main(void) {
 int queued, before, epoch_before, i;
 // Initialized defaults / no saved combo are NOT migration evidence.
 intent=-1; map_epoch(); WP_AccountKnifeReady(0); WP_RestoreKnife(); assert(intent==-1 && equips==0);
 // Account response late: frames before the accepted load cannot equip defaults.
 map_epoch(); WP_RestoreKnife(); time=10; WP_RestoreKnife(); assert(equips==0);
 // Previously saved enabled combo migrates, then requires own spawned stats.
 WP_AccountKnifeReady(1); assert(intent==1 && wp_restoreknife);
 mine=0; WP_RestoreKnife(); assert(equips==0);
 mine=1; health=0; WP_RestoreKnife(); assert(equips==0);
 health=100; WP_RestoreKnife(); assert(equips==1 && wp_restoreknife);
 // Retry only after cadence; stop only on actual server selection.
 WP_RestoreKnife(); assert(equips==1); time=11; WP_RestoreKnife(); assert(equips==2);
 weapon=1; WP_RestoreKnife(); assert(!wp_restoreknife); time=12; WP_RestoreKnife(); assert(equips==2);
 // Next map restores remembered intent only after account readiness.
 map_epoch(); WP_RestoreKnife(); assert(equips==2); WP_AccountKnifeReady(1); WP_RestoreKnife(); assert(equips==3);
 // Explicit Drop preserves cosmetics (no cosmetic cvar may reach our stub).
 WP_Drop(); assert(intent==0 && drops==1 && !wp_restoreknife);
 map_epoch(); WP_AccountKnifeReady(1); WP_RestoreKnife(); assert(intent==0 && equips==3);
 // A late accepted cloud load must not undo an explicit local Drop.
 WP_AccountKnifeReady(1); WP_RestoreKnife(); assert(intent==0 && equips==3);
 // Next explicit workshop/knife selection re-enables, without changing visibility.
 WP_EquipKnife(); assert(intent==1 && wp_restoreknife); WP_RestoreKnife(); assert(equips==4);
 map_epoch(); WP_AccountKnifeReady(0); WP_RestoreKnife(); assert(equips==5);
 // A gun selected before restore is authoritative, never replaced by the pump.
 map_epoch(); weapon=4; WP_AccountKnifeReady(1); WP_RestoreKnife(); assert(equips==5 && !wp_restoreknife);
 // Pending explicit gun with zero stat must defeat a later account response.
 map_epoch(); intent=1; WP_CancelKnifeChoice(); localcmd("cmd weapon 4\n"); assert(guns==1 && weapon==0);
 WP_AccountKnifeReady(1); WP_RestoreKnife(); assert(equips==5 && !wp_restoreknife && intent==1);
 // A queued old choice cannot re-enable Drop or touch the model-choice seam.
 map_epoch(); WP_CancelKnifeChoice(); queued=wp_choiceepoch; WP_Drop(); before=equips;
 WP_CompleteKnifeChoice(0,queued); assert(completed==0 && equips==before && intent==0);
 // A genuinely later successful selection does re-enable, with a real request.
 WP_CancelKnifeChoice(); queued=wp_choiceepoch; WP_CompleteKnifeChoice(0,queued);
 assert(completed==1 && intent==1 && equips==before+1);
 // Likewise a queued choice must not replace a newer explicit gun command.
 WP_CancelKnifeChoice(); queued=wp_choiceepoch; WP_CancelKnifeChoice(); localcmd("cmd weapon 4\n"); before=equips;
 WP_CompleteKnifeChoice(0,queued); assert(completed==1 && equips==before);
 // Newer queued catalog choice wins; an old completion cannot consume it.
 WP_CancelKnifeChoice(); queued=wp_choiceepoch; WP_CancelKnifeChoice();
 WP_CompleteKnifeChoice(0,queued); assert(completed==1);
 WP_CompleteKnifeChoice(0,wp_choiceepoch); assert(completed==2);
 // Unsupported server: no automatic loop; explicit one-shot remains possible.
 map_epoch(); capability=""; WP_EquipKnife(); before=equips;
 WP_RestoreKnife(); time=2; WP_RestoreKnife(); assert(equips==before);
 localcmd("cmd weapon knife\n"); assert(equips==before+1);
 // Cold restored knife: failed load is latched; still missing cannot spin work.
 map_epoch(); intent=1; weapon=1; wp_model=""; wp_weapon=0; available=0;
 ordinary_frame(); assert(!wp_ready && wp_modelmissing && mounts==1 && probes==1);
 WP_RetryMountedKnife(); assert(!wp_ready && wp_modelmissing && freed==0 && probes==2);
 for(i=0;i<20;i++) { ordinary_frame(); }
 assert(mounts==1 && probes==2 && loads==0);
 // Mount success must reopen only this failed cache, then ordinary load acts.
 available=1; before=equips; epoch_before=wp_choiceepoch; WP_RetryMountedKnife();
 assert(!strcmp(wp_model,"") && freed==1 && !wp_modelmissing);
 assert(intent==1 && equips==before && wp_choiceepoch==epoch_before);
 ordinary_frame(); assert(wp_ready && loads==1 && mounts==1);
 WP_RetryMountedKnife(); for(i=0;i<20;i++) { ordinary_frame(); }
 assert(loads==1 && mounts==1 && probes==4 && freed==1);
 // Ready newer gun and Drop cannot be disturbed by old readiness callbacks.
 wp_modelmissing=1; wp_weapon=4; weapon=4; wp_ready=1; before=probes;
 WP_RetryMountedKnife(); assert(probes==before && freed==1 && wp_ready);
 wp_weapon=weapon=1; wp_ready=0; wp_model=current_model; WP_Drop(); epoch_before=wp_choiceepoch;
 WP_RetryMountedKnife(); assert(probes==before && freed==1 && intent==0 && wp_choiceepoch==epoch_before);
 // A callback for an old failed model cannot clear a newer selected model.
 intent=1; wp_model="models/old-knife.mdl"; WP_RetryMountedKnife(); assert(probes==before && freed==1);
 puts("PASS knife helpers: prior equip/ordering/capability controls plus cold missing model, mount recovery, ordinary retry, still-missing/no-repeat, ready gun, Drop and model identity; source wiring 17 controls");
 return 0;
}
'''
    env = os.environ.copy()
    env["PATH"] = str(Path(args.compiler).parent) + os.pathsep + env.get("PATH", "")
    variants = {"subject": helpers}
    for name, guard in (
        ("control-late-account", "\tif (wp_explicitchoice) return;"),
        ("control-stale-completion", "\tif (epoch != wp_choiceepoch) return;"),
        ("control-absent-capability", '\tif (strcmp(serverkey("*vmsetup"), "1")) return;'),
    ):
        assert helpers.count(guard) == 1
        # Leave expressions referenced so strict -Werror remains identical.
        variants[name] = helpers.replace(guard, guard.replace(" return;", " {}"))
    assert helpers.count('\twp_model = "";') == 1
    variants["control-cold-retry"] = helpers.replace('\twp_model = "";', '\t/* disabled failed-cache invalidation */')
    for name, code in variants.items():
        source = args.work_root / (name + ".c")
        exe = args.work_root / (name + ".exe")
        source.write_text(prefix + code + tests)
        result = subprocess.run([args.compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(exe)], env=env, capture_output=True, text=True)
        (args.work_root / (name + "-compile.log")).write_text(result.stdout + result.stderr)
        result.check_returncode()
        result = subprocess.run([str(exe)], env=env, capture_output=True, text=True)
        (args.work_root / (name + "-result.log")).write_text(result.stdout + result.stderr)
        if name == "subject":
            print(result.stdout, end="")
            result.check_returncode()
        else:
            assert result.returncode != 0, name + " failed to detect disabled guard"
            print(name + ": intended assertion failure detected")


if __name__ == "__main__":
    main()
