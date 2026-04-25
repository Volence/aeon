#!/usr/bin/env python3
"""
Tests for s4lint — Sonic 4 Engine 68000 assembly linter.

Run with: python3 -m pytest tools/test_s4lint.py -v
      or: python3 tools/test_s4lint.py
"""

import sys
import os
import unittest

# Allow running from the s4_engine root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.s4lint import (
    tokenize_line, Token, Diagnostic, LintContext,
    parse_numeric, _extract_address_value,
    check_e001, check_e002, check_e003, check_e004,
    check_e005_track, _count_dc_b_items, _count_ds_b_items,
    run_checks, _parse_suppressed,
)


class TestTokenizer(unittest.TestCase):

    # ------------------------------------------------------------------
    # Basic instructions
    # ------------------------------------------------------------------

    def test_instruction_with_size_and_operands(self):
        tok = tokenize_line("    move.w  d0, (a0)+")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "move")
        self.assertEqual(tok.size, ".w")
        self.assertEqual(tok.operands, ["d0", "(a0)+"])
        self.assertEqual(tok.comment, "")

    def test_no_size_instruction(self):
        """rts has no size suffix."""
        tok = tokenize_line("        rts")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "rts")
        self.assertEqual(tok.size, "")
        self.assertEqual(tok.operands, [])
        self.assertEqual(tok.comment, "")

    def test_instruction_with_comment(self):
        tok = tokenize_line("        rts                    ; return")
        self.assertEqual(tok.instruction, "rts")
        self.assertEqual(tok.comment, "; return")

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def test_global_label_alone(self):
        tok = tokenize_line("EntryPoint:")
        self.assertEqual(tok.label, "EntryPoint")
        self.assertEqual(tok.instruction, "")
        self.assertEqual(tok.operands, [])

    def test_local_label_alone(self):
        tok = tokenize_line(".wait_z80:")
        self.assertEqual(tok.label, ".wait_z80")
        self.assertEqual(tok.instruction, "")

    def test_indented_local_label(self):
        """Local labels may appear indented in this codebase."""
        tok = tokenize_line("    .loop:")
        self.assertEqual(tok.label, ".loop")
        self.assertEqual(tok.instruction, "")

    def test_label_plus_instruction(self):
        """Label + instruction on same line."""
        tok = tokenize_line("Init:   moveq   #0, d0")
        self.assertEqual(tok.label, "Init")
        self.assertEqual(tok.instruction, "moveq")
        self.assertEqual(tok.size, "")
        self.assertEqual(tok.operands, ["#0", "d0"])

    def test_label_plus_sized_instruction(self):
        tok = tokenize_line("Cold_Boot: move.l  #$53454741, (TMSS_REGISTER).l")
        self.assertEqual(tok.label, "Cold_Boot")
        self.assertEqual(tok.instruction, "move")
        self.assertEqual(tok.size, ".l")
        self.assertEqual(tok.operands, ["#$53454741", "(TMSS_REGISTER).l"])

    # ------------------------------------------------------------------
    # Comments and blank lines
    # ------------------------------------------------------------------

    def test_comment_only_line(self):
        tok = tokenize_line("; This is a comment")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "")
        self.assertEqual(tok.operands, [])
        self.assertEqual(tok.comment, "; This is a comment")

    def test_blank_line(self):
        tok = tokenize_line("")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "")
        self.assertEqual(tok.operands, [])
        self.assertEqual(tok.comment, "")

    def test_whitespace_only_line(self):
        tok = tokenize_line("    ")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "")
        self.assertEqual(tok.operands, [])

    # ------------------------------------------------------------------
    # Directives
    # ------------------------------------------------------------------

    def test_dc_w(self):
        tok = tokenize_line("    dc.w    $0000")
        self.assertEqual(tok.instruction, "dc")
        self.assertEqual(tok.size, ".w")
        self.assertEqual(tok.operands, ["$0000"])

    def test_dc_b(self):
        tok = tokenize_line('    dc.b    "SEGA GENESIS    "')
        self.assertEqual(tok.instruction, "dc")
        self.assertEqual(tok.size, ".b")
        # The string is one operand
        self.assertTrue(any('"SEGA GENESIS    "' in op for op in tok.operands))

    def test_dc_l_multiple(self):
        tok = tokenize_line("    dc.l    SYSTEM_STACK, EntryPoint")
        self.assertEqual(tok.instruction, "dc")
        self.assertEqual(tok.size, ".l")
        self.assertEqual(tok.operands, ["SYSTEM_STACK", "EntryPoint"])

    def test_ds_b(self):
        tok = tokenize_line("vdp_mode1               ds.b 1")
        self.assertEqual(tok.label, "vdp_mode1")
        self.assertEqual(tok.instruction, "ds")
        self.assertEqual(tok.size, ".b")
        self.assertEqual(tok.operands, ["1"])

    def test_include_directive(self):
        tok = tokenize_line('    include "constants.asm"')
        self.assertEqual(tok.instruction, "include")
        self.assertEqual(tok.size, "")
        self.assertEqual(tok.operands, ['"constants.asm"'])

    def test_even_directive(self):
        tok = tokenize_line("    even")
        self.assertEqual(tok.instruction, "even")
        self.assertEqual(tok.operands, [])

    def test_align_directive(self):
        tok = tokenize_line("    align 2")
        self.assertEqual(tok.instruction, "align")
        self.assertEqual(tok.operands, ["2"])

    def test_org_directive(self):
        tok = tokenize_line("    org 0")
        self.assertEqual(tok.instruction, "org")
        self.assertEqual(tok.operands, ["0"])

    def test_cpu_directive(self):
        tok = tokenize_line("    cpu 68000")
        self.assertEqual(tok.instruction, "cpu")
        self.assertEqual(tok.operands, ["68000"])

    def test_set_directive(self):
        """AS `set` directive — not a 68K instruction."""
        tok = tokenize_line("    set .c, 0")
        self.assertEqual(tok.instruction, "set")
        self.assertEqual(tok.operands, [".c", "0"])

    def test_error_directive(self):
        tok = tokenize_line('    error "ROM size is odd"')
        self.assertEqual(tok.instruction, "error")
        self.assertTrue(any('"ROM size is odd"' in op for op in tok.operands))

    def test_if_directive(self):
        tok = tokenize_line("    if (EndOfRom & 1) <> 0")
        self.assertEqual(tok.instruction, "if")
        self.assertGreater(len(tok.operands), 0)

    def test_endif_directive(self):
        tok = tokenize_line("    endif")
        self.assertEqual(tok.instruction, "endif")
        self.assertEqual(tok.operands, [])

    def test_ifdef_directive(self):
        tok = tokenize_line("    ifdef _dplc_ptr")
        self.assertEqual(tok.instruction, "ifdef")
        self.assertEqual(tok.operands, ["_dplc_ptr"])

    def test_ifndef_directive(self):
        tok = tokenize_line("    ifndef _dplc_ptr")
        self.assertEqual(tok.instruction, "ifndef")
        self.assertEqual(tok.operands, ["_dplc_ptr"])

    def test_rept_directive(self):
        tok = tokenize_line("    rept 4")
        self.assertEqual(tok.instruction, "rept")
        self.assertEqual(tok.operands, ["4"])

    def test_endr_directive(self):
        tok = tokenize_line("    endr")
        self.assertEqual(tok.instruction, "endr")

    def test_struct_directive(self):
        """AS struct: label before the directive keyword."""
        tok = tokenize_line("VDP_Shadow struct")
        self.assertEqual(tok.label, "VDP_Shadow")
        self.assertEqual(tok.instruction, "struct")
        self.assertEqual(tok.operands, [])

    def test_endstruct_directive(self):
        tok = tokenize_line("VDP_Shadow endstruct")
        self.assertEqual(tok.label, "VDP_Shadow")
        self.assertEqual(tok.instruction, "endstruct")

    def test_binclude_directive(self):
        """Uppercase BINCLUDE variant used in this codebase."""
        tok = tokenize_line('    BINCLUDE "data/mappings/sonic.bin"')
        self.assertEqual(tok.instruction, "BINCLUDE")
        self.assertTrue(any('"data/mappings/sonic.bin"' in op for op in tok.operands))

    def test_phase_directive(self):
        tok = tokenize_line("    phase $FF0000")
        self.assertEqual(tok.instruction, "phase")
        self.assertEqual(tok.operands, ["$FF0000"])

    def test_dephase_directive(self):
        tok = tokenize_line("    dephase")
        self.assertEqual(tok.instruction, "dephase")
        self.assertEqual(tok.operands, [])

    # ------------------------------------------------------------------
    # Macros
    # ------------------------------------------------------------------

    def test_macro_no_args(self):
        """stopZ80 is a macro — preserve case, no operands."""
        tok = tokenize_line("        stopZ80")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "stopZ80")
        self.assertEqual(tok.size, "")
        self.assertEqual(tok.operands, [])

    def test_macro_with_args(self):
        """setVDPReg macro with two arguments."""
        tok = tokenize_line("        setVDPReg VDP_Shadow_vdp_mode2, #$34")
        self.assertEqual(tok.instruction, "setVDPReg")
        self.assertEqual(tok.operands, ["VDP_Shadow_vdp_mode2", "#$34"])

    # ------------------------------------------------------------------
    # Operand splitting edge cases
    # ------------------------------------------------------------------

    def test_operand_parens_not_split(self):
        """Parenthesised addressing modes must not be split on inner comma."""
        tok = tokenize_line("        move.l  (a0,d0.w), d1")
        self.assertEqual(tok.instruction, "move")
        self.assertEqual(tok.size, ".l")
        self.assertEqual(tok.operands, ["(a0,d0.w)", "d1"])

    def test_movem_register_list(self):
        """movem register list — dash is fine, comma separates two operands."""
        tok = tokenize_line("        movem.l d0-a6, -(sp)")
        self.assertEqual(tok.instruction, "movem")
        self.assertEqual(tok.size, ".l")
        self.assertEqual(tok.operands, ["d0-a6", "-(sp)"])

    def test_nested_parens(self):
        """Function calls in operands — e.g. #vram_art(VRAM_X,0,0)."""
        tok = tokenize_line("        move.w  #vram_art(VRAM_Sonic,0,0), SST_art_tile(a0)")
        self.assertEqual(tok.instruction, "move")
        self.assertEqual(tok.size, ".w")
        self.assertEqual(tok.operands, ["#vram_art(VRAM_Sonic,0,0)", "SST_art_tile(a0)"])

    # ------------------------------------------------------------------
    # Assignment / EQU lines
    # ------------------------------------------------------------------

    def test_simple_assignment(self):
        """MY_CONST = $50 — label is lvalue, instruction is '='."""
        tok = tokenize_line("MY_CONST = $50")
        self.assertEqual(tok.label, "MY_CONST")
        self.assertEqual(tok.instruction, "=")
        self.assertEqual(tok.operands, ["$50"])

    def test_assignment_with_expression(self):
        """Assignment where the rhs references another constant."""
        tok = tokenize_line("_enemy_patrol_left = SST_sst_custom")
        self.assertEqual(tok.label, "_enemy_patrol_left")
        self.assertEqual(tok.instruction, "=")
        self.assertEqual(tok.operands, ["SST_sst_custom"])

    def test_assignment_with_offset(self):
        tok = tokenize_line("_art_base       = SST_sst_custom+4")
        self.assertEqual(tok.label, "_art_base")
        self.assertEqual(tok.instruction, "=")
        self.assertEqual(tok.operands, ["SST_sst_custom+4"])

    def test_padToPowerOfTwo_assignment(self):
        """Top-level flag assignment from main.asm."""
        tok = tokenize_line("padToPowerOfTwo         = 1")
        self.assertEqual(tok.label, "padToPowerOfTwo")
        self.assertEqual(tok.instruction, "=")
        self.assertEqual(tok.operands, ["1"])

    # ------------------------------------------------------------------
    # Lint suppression comment
    # ------------------------------------------------------------------

    def test_suppress_comment_recognized(self):
        """'; lint: disable=E002' is captured verbatim in comment field."""
        tok = tokenize_line("        rts                    ; lint: disable=E002")
        self.assertEqual(tok.instruction, "rts")
        self.assertIn("lint: disable=E002", tok.comment)

    # ------------------------------------------------------------------
    # Real patterns from this codebase
    # ------------------------------------------------------------------

    def test_dbf_instruction(self):
        tok = tokenize_line("        dbf     d1, .vdp_loop")
        self.assertEqual(tok.instruction, "dbf")
        self.assertEqual(tok.operands, ["d1", ".vdp_loop"])

    def test_bne_local_label(self):
        tok = tokenize_line("        bne.s   .wait_z80")
        self.assertEqual(tok.instruction, "bne")
        self.assertEqual(tok.size, ".s")
        self.assertEqual(tok.operands, [".wait_z80"])

    def test_lea_instruction(self):
        tok = tokenize_line("        lea     (Object_RAM).w, a0")
        self.assertEqual(tok.instruction, "lea")
        self.assertEqual(tok.operands, ["(Object_RAM).w", "a0"])

    def test_move_with_absolute_long(self):
        tok = tokenize_line("        move.w  (Z80_BUS_REQUEST).l, d0")
        self.assertEqual(tok.instruction, "move")
        self.assertEqual(tok.size, ".w")
        self.assertEqual(tok.operands, ["(Z80_BUS_REQUEST).l", "d0"])

    def test_btst_instruction(self):
        tok = tokenize_line("        btst    #0, (Z80_BUS_REQUEST).l")
        self.assertEqual(tok.instruction, "btst")
        self.assertEqual(tok.operands, ["#0", "(Z80_BUS_REQUEST).l"])

    def test_movem_restore(self):
        tok = tokenize_line("        movem.l (sp)+, d0-d2/a1")
        self.assertEqual(tok.instruction, "movem")
        self.assertEqual(tok.size, ".l")
        self.assertEqual(tok.operands, ["(sp)+", "d0-d2/a1"])

    def test_jsr_instruction(self):
        tok = tokenize_line("        jsr     AllocDynamic")
        self.assertEqual(tok.instruction, "jsr")
        self.assertEqual(tok.operands, ["AllocDynamic"])

    def test_exg_instruction(self):
        tok = tokenize_line("        exg     a1, a2")
        self.assertEqual(tok.instruction, "exg")
        self.assertEqual(tok.operands, ["a1", "a2"])

    def test_macro_definition_line(self):
        """'stopZ80 macro' — the macro keyword itself."""
        tok = tokenize_line("stopZ80 macro")
        self.assertEqual(tok.label, "stopZ80")
        self.assertEqual(tok.instruction, "macro")
        self.assertEqual(tok.operands, [])

    def test_endm_directive(self):
        tok = tokenize_line("        endm")
        self.assertEqual(tok.instruction, "endm")
        self.assertEqual(tok.operands, [])

    def test_padding_off(self):
        tok = tokenize_line("    padding off")
        self.assertEqual(tok.instruction, "padding")
        self.assertEqual(tok.operands, ["off"])

    def test_supmode_on(self):
        tok = tokenize_line("    supmode on")
        self.assertEqual(tok.instruction, "supmode")
        self.assertEqual(tok.operands, ["on"])

    def test_function_definition(self):
        """AS `function` keyword — multi-line via backslash not tested here,
        just the first line."""
        tok = tokenize_line("vdpComm     function addr,type,rwd, \\")
        self.assertEqual(tok.label, "vdpComm")
        self.assertEqual(tok.instruction, "function")

    def test_line_with_comment_semicolon_in_string(self):
        """Semicolon inside a string literal must NOT start a comment."""
        tok = tokenize_line('    dc.b    "SEGA; GENESIS"   ; comment')
        self.assertEqual(tok.instruction, "dc")
        self.assertIn("; comment", tok.comment)
        # The operand should contain the full string including the semicolon
        self.assertTrue(any('"SEGA; GENESIS"' in op for op in tok.operands))


class TestDiagnostic(unittest.TestCase):

    def test_str_format(self):
        d = Diagnostic("boot.asm", 42, "error", "E001", "unsized branch detected")
        self.assertEqual(str(d), "boot.asm:42: error: unsized branch detected [E001]")

    def test_warning_format(self):
        d = Diagnostic("core.asm", 7, "warning", "W003", "possible fall-through")
        self.assertEqual(str(d), "core.asm:7: warning: possible fall-through [W003]")


class TestLintContext(unittest.TestCase):

    def test_emit_adds_diagnostic(self):
        ctx = LintContext("boot.asm", {})
        ctx.emit("error", "E001", 10, "test message")
        self.assertEqual(len(ctx.diagnostics), 1)
        self.assertEqual(ctx.diagnostics[0].code, "E001")
        self.assertEqual(ctx.diagnostics[0].severity, "error")

    def test_reset_routine_state(self):
        ctx = LintContext("boot.asm", {})
        ctx.z80_state = "stopped"
        ctx.ints_state = "disabled"
        ctx.sr_saved = True
        ctx.reset_routine_state()
        self.assertEqual(ctx.z80_state, "running")
        self.assertEqual(ctx.ints_state, "enabled")
        self.assertFalse(ctx.sr_saved)

    def test_initial_state(self):
        ctx = LintContext("boot.asm", {})
        self.assertEqual(ctx.z80_state, "running")
        self.assertEqual(ctx.ints_state, "enabled")
        self.assertFalse(ctx.sr_saved)
        self.assertFalse(ctx.in_struct)
        self.assertFalse(ctx.in_rept)
        self.assertFalse(ctx.in_macro_def)


# ---------------------------------------------------------------------------
# Helpers for check tests
# ---------------------------------------------------------------------------

def _make_ctx(filepath="engine/core.asm"):
    """Create a minimal LintContext for check tests."""
    return LintContext(filepath, {})


def _run_check(check_fn, line_text, filepath="engine/core.asm", suppressed=None):
    """Tokenize *line_text*, run *check_fn*, return list of diagnostics."""
    if suppressed is None:
        suppressed = set()
    ctx = _make_ctx(filepath)
    tok = tokenize_line(line_text)
    check_fn(ctx, tok, 1, suppressed)
    return ctx.diagnostics


# ---------------------------------------------------------------------------
# parse_numeric / _extract_address_value helpers
# ---------------------------------------------------------------------------

class TestParseNumeric(unittest.TestCase):

    def test_hex_dollar(self):
        self.assertEqual(parse_numeric("$C00000"), 0xC00000)

    def test_hex_lowercase(self):
        self.assertEqual(parse_numeric("$ff0000"), 0xFF0000)

    def test_decimal(self):
        self.assertEqual(parse_numeric("42"), 42)

    def test_odd_hex(self):
        self.assertEqual(parse_numeric("$C00001"), 0xC00001)

    def test_non_numeric_returns_none(self):
        self.assertIsNone(parse_numeric("MyLabel"))

    def test_expression_returns_none(self):
        self.assertIsNone(parse_numeric("$FF0000+4"))

    def test_zero(self):
        self.assertEqual(parse_numeric("0"), 0)


class TestExtractAddressValue(unittest.TestCase):

    def test_plain_hex(self):
        self.assertEqual(_extract_address_value("$FF0000"), 0xFF0000)

    def test_parens_with_suffix(self):
        self.assertEqual(_extract_address_value("($C00004).l"), 0xC00004)

    def test_parens_without_suffix(self):
        self.assertEqual(_extract_address_value("($FF0000)"), 0xFF0000)

    def test_w_suffix_no_parens(self):
        self.assertEqual(_extract_address_value("$FF0000.w"), 0xFF0000)

    def test_symbolic_returns_none(self):
        self.assertIsNone(_extract_address_value("(VDP_CTRL).l"))

    def test_symbolic_plain_returns_none(self):
        self.assertIsNone(_extract_address_value("Object_RAM"))

    def test_immediate_hash_returns_none(self):
        """Immediate operands (#value) are not addresses — ignore."""
        self.assertIsNone(_extract_address_value("#$C00000"))


# ---------------------------------------------------------------------------
# E001: Unsized branch or jump
# ---------------------------------------------------------------------------

class TestE001_UnsizedBranch(unittest.TestCase):

    def _errors(self, line, filepath="engine/core.asm", suppressed=None):
        diags = _run_check(check_e001, line, filepath, suppressed or set())
        return [d for d in diags if d.code == "E001"]

    # --- should fire ---

    def test_bra_no_size(self):
        errs = self._errors("        bra     .loop")
        self.assertEqual(len(errs), 1)
        self.assertIn("bra", errs[0].message)

    def test_beq_no_size(self):
        errs = self._errors("        beq     .done")
        self.assertEqual(len(errs), 1)

    def test_bne_no_size(self):
        errs = self._errors("        bne     .retry")
        self.assertEqual(len(errs), 1)

    def test_bsr_no_size(self):
        errs = self._errors("        bsr     Subroutine")
        self.assertEqual(len(errs), 1)

    def test_bhi_no_size(self):
        errs = self._errors("        bhi     .over")
        self.assertEqual(len(errs), 1)

    def test_bmi_no_size(self):
        errs = self._errors("        bmi     .neg")
        self.assertEqual(len(errs), 1)

    def test_bcc_no_size(self):
        errs = self._errors("        bcc     .ok")
        self.assertEqual(len(errs), 1)

    # --- should NOT fire ---

    def test_bra_s_ok(self):
        errs = self._errors("        bra.s   .loop")
        self.assertEqual(len(errs), 0)

    def test_bne_w_ok(self):
        errs = self._errors("        bne.w   .far_label")
        self.assertEqual(len(errs), 0)

    def test_beq_s_ok(self):
        errs = self._errors("        beq.s   .done")
        self.assertEqual(len(errs), 0)

    def test_jmp_not_checked(self):
        """jmp is always long — not in the E001 set."""
        errs = self._errors("        jmp     (a0)")
        self.assertEqual(len(errs), 0)

    def test_jsr_not_checked(self):
        errs = self._errors("        jsr     SomeRoutine")
        self.assertEqual(len(errs), 0)

    def test_dbf_not_checked(self):
        errs = self._errors("        dbf     d1, .loop")
        self.assertEqual(len(errs), 0)

    def test_dbra_not_checked(self):
        errs = self._errors("        dbra    d0, .wait")
        self.assertEqual(len(errs), 0)

    def test_suppressed_e001(self):
        errs = self._errors("        bra     .loop", suppressed={"E001"})
        self.assertEqual(len(errs), 0)

    def test_non_branch_not_checked(self):
        errs = self._errors("        move.w  d0, d1")
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# E002: Multiply / divide in hot path
# ---------------------------------------------------------------------------

class TestE002_MultiplyDivide(unittest.TestCase):

    def _diags(self, line, filepath="engine/core.asm", suppressed=None):
        diags = _run_check(check_e002, line, filepath, suppressed or set())
        return diags

    # --- engine/ → error ---

    def test_mulu_in_engine_is_error(self):
        diags = self._diags("        mulu    #8, d0", filepath="engine/core.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_muls_in_engine_is_error(self):
        diags = self._diags("        muls    d1, d0", filepath="engine/physics.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_divu_in_engine_is_error(self):
        diags = self._diags("        divu    #10, d0", filepath="engine/math.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_divs_in_engine_is_error(self):
        diags = self._diags("        divs    d2, d1", filepath="engine/scroll.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    # --- objects/ → error ---

    def test_mulu_in_objects_is_error(self):
        diags = self._diags("        mulu    #4, d0", filepath="objects/player.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_divs_in_objects_is_error(self):
        diags = self._diags("        divs    d0, d1", filepath="objects/enemy.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    # --- other directories → warning W014 ---

    def test_mulu_in_init_is_warning(self):
        diags = self._diags("        mulu    #8, d0", filepath="init/boot.asm")
        warns = [d for d in diags if d.code == "W014" and d.severity == "warning"]
        self.assertEqual(len(warns), 1)

    def test_muls_in_data_is_warning(self):
        diags = self._diags("        muls    d0, d1", filepath="data/tables.asm")
        warns = [d for d in diags if d.code == "W014" and d.severity == "warning"]
        self.assertEqual(len(warns), 1)

    # --- not flagged ---

    def test_add_not_flagged(self):
        diags = self._diags("        add.w   d0, d1", filepath="engine/core.asm")
        self.assertEqual(len(diags), 0)

    def test_suppressed_e002(self):
        diags = self._diags("        mulu    #8, d0", filepath="engine/core.asm",
                             suppressed={"E002"})
        errs = [d for d in diags if d.code == "E002"]
        self.assertEqual(len(errs), 0)

    def test_suppressed_w014(self):
        diags = self._diags("        mulu    #8, d0", filepath="init/boot.asm",
                             suppressed={"W014"})
        warns = [d for d in diags if d.code == "W014"]
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# E003: Odd immediate address
# ---------------------------------------------------------------------------

class TestE003_OddAddress(unittest.TestCase):

    def _errors(self, line, filepath="engine/core.asm", suppressed=None):
        diags = _run_check(check_e003, line, filepath, suppressed or set())
        return [d for d in diags if d.code == "E003"]

    # --- should fire ---

    def test_lea_odd_address(self):
        errs = self._errors("        lea     ($FF0001).l, a0")
        self.assertEqual(len(errs), 1)

    def test_movea_odd_address(self):
        errs = self._errors("        movea.l ($C00003).l, a1")
        self.assertEqual(len(errs), 1)

    def test_jmp_odd_address(self):
        errs = self._errors("        jmp     ($1001).l")
        self.assertEqual(len(errs), 1)

    def test_jsr_odd_address(self):
        errs = self._errors("        jsr     ($1003).l")
        self.assertEqual(len(errs), 1)

    def test_lea_odd_plain_hex(self):
        errs = self._errors("        lea     $FF0001, a0")
        self.assertEqual(len(errs), 1)

    # --- should NOT fire ---

    def test_lea_even_address(self):
        errs = self._errors("        lea     ($FF0000).l, a0")
        self.assertEqual(len(errs), 0)

    def test_movea_even_address(self):
        errs = self._errors("        movea.l ($C00004).l, a1")
        self.assertEqual(len(errs), 0)

    def test_lea_symbolic_not_flagged(self):
        errs = self._errors("        lea     (Object_RAM).w, a0")
        self.assertEqual(len(errs), 0)

    def test_movea_symbolic_not_flagged(self):
        errs = self._errors("        movea.l (VDP_CTRL).l, a0")
        self.assertEqual(len(errs), 0)

    def test_move_not_checked_by_e003(self):
        """E003 only checks movea/lea/jmp/jsr — plain move is E004 territory."""
        errs = self._errors("        move.w  ($C00001).l, d0")
        self.assertEqual(len(errs), 0)

    def test_suppressed_e003(self):
        errs = self._errors("        lea     ($FF0001).l, a0", suppressed={"E003"})
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# E004: Word/long access to odd literal address
# ---------------------------------------------------------------------------

class TestE004_OddWordAccess(unittest.TestCase):

    def _errors(self, line, filepath="engine/core.asm", suppressed=None):
        diags = _run_check(check_e004, line, filepath, suppressed or set())
        return [d for d in diags if d.code == "E004"]

    # --- should fire ---

    def test_move_w_odd_src(self):
        errs = self._errors("        move.w  ($C00001).l, d0")
        self.assertEqual(len(errs), 1)

    def test_move_w_odd_dst(self):
        errs = self._errors("        move.w  d0, ($C00001).l")
        self.assertEqual(len(errs), 1)

    def test_move_l_odd_address(self):
        errs = self._errors("        move.l  ($FF0003).l, d0")
        self.assertEqual(len(errs), 1)

    def test_add_w_odd_address(self):
        errs = self._errors("        add.w   ($FF0001).l, d0")
        self.assertEqual(len(errs), 1)

    def test_move_w_plain_odd_hex(self):
        errs = self._errors("        move.w  $FF0001, d0")
        self.assertEqual(len(errs), 1)

    # --- should NOT fire ---

    def test_move_b_odd_ok(self):
        """Byte access to odd address is legal."""
        errs = self._errors("        move.b  ($C00001).l, d0")
        self.assertEqual(len(errs), 0)

    def test_move_w_even_ok(self):
        errs = self._errors("        move.w  ($C00004).l, d0")
        self.assertEqual(len(errs), 0)

    def test_move_l_even_ok(self):
        errs = self._errors("        move.l  ($FF0000).l, d0")
        self.assertEqual(len(errs), 0)

    def test_move_w_symbolic_not_flagged(self):
        errs = self._errors("        move.w  (VDP_DATA).l, d0")
        self.assertEqual(len(errs), 0)

    def test_move_no_size_not_flagged(self):
        """Without explicit .w or .l size we cannot determine access width."""
        errs = self._errors("        move    d0, d1")
        self.assertEqual(len(errs), 0)

    def test_suppressed_e004(self):
        errs = self._errors("        move.w  ($C00001).l, d0", suppressed={"E004"})
        self.assertEqual(len(errs), 0)

    def test_dc_w_not_checked(self):
        """dc.w is a directive, not an instruction accessing memory."""
        errs = self._errors("        dc.w    $0001")
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# E005: Missing alignment after byte data
# ---------------------------------------------------------------------------

class TestE005_MissingEven(unittest.TestCase):
    """Tests for E005: dc.w/dc.l/ds.w/ds.l or 68K instruction after an odd
    number of dc.b/ds.b bytes without an intervening even/align."""

    def _lint_lines(self, lines_str: str):
        """Process multi-line assembly string; return list of E005 Diagnostics."""
        ctx = LintContext("test.asm", {})
        for line_num, raw_line in enumerate(lines_str.split("\n"), start=1):
            token = tokenize_line(raw_line)
            run_checks(ctx, token, line_num, raw_line, set())
        return [d for d in ctx.diagnostics if d.code == "E005"]

    # --- helper unit tests ---

    def test_count_dc_b_simple(self):
        self.assertEqual(_count_dc_b_items(["1", "2", "3"]), 3)

    def test_count_dc_b_string(self):
        self.assertEqual(_count_dc_b_items(['\"SEGA\"']), 4)

    def test_count_dc_b_mixed(self):
        self.assertEqual(_count_dc_b_items(["0", '\"SEGA\"']), 5)

    def test_count_ds_b_decimal(self):
        self.assertEqual(_count_ds_b_items(["3"]), 3)

    def test_count_ds_b_hex(self):
        self.assertEqual(_count_ds_b_items(["$04"]), 4)

    def test_count_ds_b_unknown_returns_zero(self):
        self.assertEqual(_count_ds_b_items(["SYMBOL"]), 0)

    # --- integration tests ---

    def test_odd_dc_b_then_dc_w_fires(self):
        """1 dc.b byte followed by dc.w -> E005."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 1)

    def test_even_dc_b_then_dc_w_ok(self):
        """2 dc.b bytes then dc.w -> no error."""
        errs = self._lint_lines("Routine:\n    dc.b    1, 2\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_odd_dc_b_even_dc_w_ok(self):
        """1 dc.b byte + even -> dc.w -> no error."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    even\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_odd_dc_b_align2_dc_w_ok(self):
        """1 dc.b byte + align 2 -> dc.w -> no error."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    align 2\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_ds_b_odd_count_then_dc_w_fires(self):
        """ds.b 3 (odd) then dc.w -> E005."""
        errs = self._lint_lines("Routine:\n    ds.b    3\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 1)

    def test_ds_b_even_count_then_dc_w_ok(self):
        """ds.b 4 (even) then dc.w -> no error."""
        errs = self._lint_lines("Routine:\n    ds.b    4\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_accumulate_multiple_dc_b_to_odd_fires(self):
        """Two dc.b lines accumulating to odd -> E005 at dc.w."""
        errs = self._lint_lines("Routine:\n    dc.b    1, 2\n    dc.b    3\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 1)

    def test_accumulate_multiple_dc_b_to_even_ok(self):
        """Two dc.b lines accumulating to even -> no error."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    dc.b    2\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_instruction_after_odd_bytes_fires(self):
        """68K instruction after 1 dc.b byte -> E005."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    nop\n")
        self.assertEqual(len(errs), 1)

    def test_dc_l_after_odd_bytes_fires(self):
        """dc.l after 1 dc.b byte -> E005."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    dc.l    $00000000\n")
        self.assertEqual(len(errs), 1)

    def test_ds_w_after_odd_bytes_fires(self):
        """ds.w after 1 dc.b byte -> E005."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    ds.w    1\n")
        self.assertEqual(len(errs), 1)

    def test_no_bytes_just_dc_w_ok(self):
        """dc.w with no preceding byte data -> no error."""
        errs = self._lint_lines("Routine:\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_string_dc_b_odd_fires(self):
        """dc.b "ABC" (3 bytes, odd) then dc.w -> E005."""
        errs = self._lint_lines('Routine:\n    dc.b    "ABC"\n    dc.w    $0000\n')
        self.assertEqual(len(errs), 1)

    def test_string_dc_b_even_ok(self):
        """dc.b "SEGA" (4 bytes, even) then dc.w -> no error."""
        errs = self._lint_lines('Routine:\n    dc.b    "SEGA"\n    dc.w    $0000\n')
        self.assertEqual(len(errs), 0)

    def test_dc_l_after_odd_ds_b_fires(self):
        """ds.b 1 (odd) then dc.l -> E005."""
        errs = self._lint_lines("Routine:\n    ds.b    1\n    dc.l    $00000000\n")
        self.assertEqual(len(errs), 1)


# ---------------------------------------------------------------------------
# Shared helper for multi-line lint tests (E006–E011)
# ---------------------------------------------------------------------------

def _lint_lines(lines_str, filepath="engine/test.asm"):
    """Process multi-line assembly string; return all Diagnostics."""
    ctx = LintContext(filepath, {})
    for i, line in enumerate(lines_str.strip().split("\n"), 1):
        t = tokenize_line(line)
        suppressed = _parse_suppressed(t.comment) if t.comment else set()
        run_checks(ctx, t, i, line, suppressed)
    return ctx.diagnostics


# ---------------------------------------------------------------------------
# E006: VDP write without Z80 stopped
# ---------------------------------------------------------------------------

class TestE006_VDPWithoutZ80(unittest.TestCase):

    def _errs(self, lines_str, filepath="engine/test.asm"):
        return [d for d in _lint_lines(lines_str, filepath) if d.code == "E006"]

    def test_vdp_ctrl_write_without_stop_fires(self):
        """Direct write to (VDP_CTRL).l without stopZ80 -> E006."""
        code = """
Routine:
        move.l  #$40000000, (VDP_CTRL).l
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)
        self.assertIn("VDP_CTRL", errs[0].message)

    def test_vdp_data_write_without_stop_fires(self):
        """Write to (VDP_DATA).l without stopZ80 -> E006."""
        code = """
Routine:
        move.l  d0, (VDP_DATA).l
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)

    def test_vdp_ctrl_write_after_stop_clean(self):
        """Write to (VDP_CTRL).l after stopZ80 -> no E006."""
        code = """
Routine:
        stopZ80
        move.l  #$40000000, (VDP_CTRL).l
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_vdp_ctrl_read_without_stop_clean(self):
        """Reading VDP_CTRL (VDP status read) -> not a write -> no E006."""
        code = """
Routine:
        move.w  (VDP_CTRL).l, d0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_vdp_hex_addr_write_without_stop_fires(self):
        """Write to ($C00004).l (literal VDP_CTRL address) without stop -> E006."""
        code = """
Routine:
        move.l  #$40000000, ($C00004).l
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)

    def test_vdp_data_hex_addr_write_without_stop_fires(self):
        """Write to ($C00000).l (literal VDP_DATA address) without stop -> E006."""
        code = """
Routine:
        move.l  d0, ($C00000).l
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)

    def test_setvdpreg_without_stop_no_e006_no_e008(self):
        """setVDPReg only writes shadow table RAM — no VDP hardware access.
        Neither E006 nor E008 should fire regardless of Z80 state."""
        code = """
Routine:
        setVDPReg vdp_mode2, #$34
        rts
"""
        diags = _lint_lines(code)
        e006 = [d for d in diags if d.code == "E006"]
        e008 = [d for d in diags if d.code == "E008"]
        self.assertEqual(len(e006), 0)
        self.assertEqual(len(e008), 0)


# ---------------------------------------------------------------------------
# E007: Unpaired stopZ80 / startZ80
# ---------------------------------------------------------------------------

class TestE007_UnpairedZ80(unittest.TestCase):

    def _errs(self, lines_str, filepath="engine/test.asm"):
        return [d for d in _lint_lines(lines_str, filepath) if d.code == "E007"]

    def test_stop_without_start_before_rts_fires(self):
        """stopZ80 with no matching startZ80 before rts -> E007."""
        code = """
Routine:
        stopZ80
        move.l  #$40000000, (VDP_CTRL).l
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)

    def test_paired_stop_start_clean(self):
        """Properly paired stopZ80/startZ80 before rts -> no E007."""
        code = """
Routine:
        stopZ80
        move.l  #$40000000, (VDP_CTRL).l
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_rts_without_stop_clean(self):
        """rts with Z80 never stopped -> no E007."""
        code = """
Routine:
        moveq   #0, d0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# E008: Macro contract violation (requires precondition not met)
# ---------------------------------------------------------------------------

class TestE008_MacroContract(unittest.TestCase):

    def _errs(self, lines_str, filepath="engine/test.asm"):
        return [d for d in _lint_lines(lines_str, filepath) if d.code == "E008"]

    def test_startz80_without_prior_stop_fires(self):
        """startZ80 when Z80 not stopped -> E008."""
        code = """
Routine:
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)
        self.assertIn("startZ80", errs[0].message)

    def test_setvdpreg_no_e008_regardless_of_z80_state(self):
        """setVDPReg writes shadow table RAM only — no VDP hardware access.
        No E008 should fire regardless of Z80 state."""
        code = """
Routine:
        setVDPReg vdp_mode2, #$34
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_setvdpreg_with_stop_also_clean(self):
        """setVDPReg after stopZ80 -> still no E008 (shadow table only)."""
        code = """
Routine:
        stopZ80
        setVDPReg vdp_mode2, #$34
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_enableints_without_disable_fires(self):
        """enableInts without prior disableInts -> E008."""
        code = """
Routine:
        enableInts
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)
        self.assertIn("enableInts", errs[0].message)

    def test_enableints_with_disable_clean(self):
        """enableInts after disableInts -> no E008."""
        code = """
Routine:
        disableInts
        enableInts
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_queuestaticdma_no_requirement_clean(self):
        """queueStaticDMA has no requires -> no E008 regardless of state."""
        code = """
Routine:
        queueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_startz80_after_stop_clean(self):
        """startZ80 after stopZ80 -> no E008."""
        code = """
Routine:
        stopZ80
        nop
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# E011: Double stopZ80
# ---------------------------------------------------------------------------

class TestE011_DoubleStop(unittest.TestCase):

    def _errs(self, lines_str, filepath="engine/test.asm"):
        return [d for d in _lint_lines(lines_str, filepath) if d.code == "E011"]

    def test_double_stopz80_fires(self):
        """Two consecutive stopZ80 calls -> E011 on the second."""
        code = """
Routine:
        stopZ80
        stopZ80
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)
        self.assertIn("stopZ80", errs[0].message)

    def test_single_stopz80_clean(self):
        """Single stopZ80 followed by startZ80 -> no E011."""
        code = """
Routine:
        stopZ80
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_stop_start_stop_clean(self):
        """stopZ80 / startZ80 / stopZ80 is valid -> no E011."""
        code = """
Routine:
        stopZ80
        startZ80
        stopZ80
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)


if __name__ == "__main__":
    unittest.main()
