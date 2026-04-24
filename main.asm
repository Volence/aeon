; Sonic 4 Engine — main assembly file
    cpu 68000
    org 0

    dc.l    $FFFFFF00
    dc.l    Entry
Entry:
    bra.s   Entry

    END
