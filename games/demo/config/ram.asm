; demo game RAM — nothing yet. TODO: your game's variables start here.
        phase Engine_RAM_End
Game_RAM_End:

        if Game_RAM_End >= SYSTEM_STACK
          error "Game RAM overflow into stack by \{Game_RAM_End - SYSTEM_STACK} bytes!"
        endif

        dephase
