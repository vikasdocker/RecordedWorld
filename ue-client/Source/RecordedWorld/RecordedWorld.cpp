#include "RecordedWorld.h"
#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY(LogRecordedWorld);

#define LOCTEXT_NAMESPACE "FRecordedWorldModule"

void FRecordedWorldModule::StartupModule()
{
	UE_LOG(LogRecordedWorld, Log, TEXT("RecordedWorld module started"));
}

void FRecordedWorldModule::ShutdownModule()
{
	UE_LOG(LogRecordedWorld, Log, TEXT("RecordedWorld module shut down"));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FRecordedWorldModule, RecordedWorld)
