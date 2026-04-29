; §4.2 Preview-zone support (streaming-integrated).
;
; Preview is now handled by Section_UpdateColumns: the streaming engine
; extends its range into neighbor section strips when the camera approaches
; a boundary. See Section_Fwd_Neighbor_Strips / Section_Bwd_Neighbor_Strips
; in ram.asm and the extended clamp logic in Section_UpdateColumns.
;
; The old direct-VDP preview routines (Section_CopyFwdPreview / _Bwd)
; have been removed — they wrote preview to fixed plane cols that were
; visible at intermediate camera positions, causing "preview leak."
