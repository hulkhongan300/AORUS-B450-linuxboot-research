// Headless: decompile every function in the current program to <outdir>/<program>.c
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;
public class ExportDecomp extends GhidraScript {
    @Override public void run() throws Exception {
        String out = getScriptArgs()[0];
        // Promote code addresses that are only referenced as data pointers (PPI/protocol
        // callback tables) into real functions so they get decompiled too.
        ghidra.program.model.mem.Memory mem = currentProgram.getMemory();
        FunctionManager fm = currentProgram.getFunctionManager();
        for (int pass = 0; pass < 3; pass++) {
            for (ghidra.program.model.address.Address a :
                    currentProgram.getReferenceManager().getReferenceDestinationIterator(currentProgram.getMinAddress(), true)) {
                ghidra.program.model.mem.MemoryBlock b = mem.getBlock(a);
                if (b == null || !b.isExecute() || fm.getFunctionContaining(a) != null) continue;
                if (getInstructionAt(a) == null) { disassemble(a); }
                if (getInstructionAt(a) != null) { createFunction(a, null); }
            }
            analyzeChanges(currentProgram);
        }
        DecompInterface d = new DecompInterface(); d.openProgram(currentProgram);
        try (PrintWriter w = new PrintWriter(new File(out, currentProgram.getName() + ".c"))) {
            w.println("// " + currentProgram.getName() + "  base=" + currentProgram.getImageBase());
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                DecompileResults r = d.decompileFunction(f, 60, monitor);
                w.println("\n// ---- " + f.getName() + " @ " + f.getEntryPoint());
                w.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// decompile failed");
            }
        }
    }
}
