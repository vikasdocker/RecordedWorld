#include "RWGameInstance.h"

URWGameInstance::URWGameInstance()
{
}

void URWGameInstance::Init()
{
	Super::Init();
	UE_LOG(LogTemp, Log, TEXT("Recorded World GameInstance initialized"));
}

void URWGameInstance::Shutdown()
{
	UE_LOG(LogTemp, Log, TEXT("Recorded World GameInstance shutdown"));
	Super::Shutdown();
}

void URWGameInstance::SetConnectionParams(const FString& Host, int32 Port, const FString& PlayerName, const FString& World)
{
	ServerHost = Host;
	ServerPort = Port;
	Username = PlayerName;
	WorldId = World;
	UE_LOG(LogTemp, Log, TEXT("Connection params: %s:%d user=%s world=%s"), *ServerHost, ServerPort, *Username, *WorldId);
}

FString URWGameInstance::GetWebSocketUrl() const
{
	return FString::Printf(TEXT("ws://%s:%d/ws/%s/%s"), *ServerHost, ServerPort, *Username, *WorldId);
}

void URWGameInstance::SetConnected(bool bConnected)
{
	bIsConnected = bConnected;
	UE_LOG(LogTemp, Log, TEXT("Connection state: %s"), bConnected ? TEXT("Connected") : TEXT("Disconnected"));
}
