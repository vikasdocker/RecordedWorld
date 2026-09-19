using UnrealBuildTool;

public class RecordedWorld : ModuleRules
{
	public RecordedWorld(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"UMG",
			"Slate",
			"SlateCore",
			"WebSockets",
			"HTTP",
			"Json",
			"JsonUtilities",
			"Landscape",
			"RenderCore",
			"RHI",
			"ProceduralMeshComponent",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
		});
	}
}
