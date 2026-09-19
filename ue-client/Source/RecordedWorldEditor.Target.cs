using UnrealBuildTool;
using System.Collections.Generic;

public class RecordedWorldEditorTarget : TargetRules
{
	public RecordedWorldEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("RecordedWorld");
		bWithLiveCoding = false;
		bOverrideBuildEnvironment = true;
	}
}
