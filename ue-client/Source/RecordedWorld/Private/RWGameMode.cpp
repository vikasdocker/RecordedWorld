#include "RWGameMode.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "WorldManager.h"
#include "RWCharacter.h"
#include "NetworkManager.h"
#include "RWHUD.h"

ARWGameMode::ARWGameMode()
{
	PrimaryActorTick.bCanEverTick = false;
	DefaultPawnClass = ARWCharacter::StaticClass();
	HUDClass = ARWHUD::StaticClass();
}

void ARWGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
	Super::InitGame(MapName, Options, ErrorMessage);
	InitializeGameSettings();
}

void ARWGameMode::StartPlay()
{
	Super::StartPlay();

	UE_LOG(LogTemp, Log, TEXT("Recorded World - GameMode started"));
	UE_LOG(LogTemp, Log, TEXT("Server: %s:%d"), *ServerHost, ServerPort);

	UWorld* World = GetWorld();
	if (World)
	{
		FActorSpawnParameters SpawnParams;
		SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		World->SpawnActor<AWorldManager>(AWorldManager::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
		UE_LOG(LogTemp, Log, TEXT("WorldManager spawned"));

		World->SpawnActor<ANetworkManager>(ANetworkManager::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
		UE_LOG(LogTemp, Log, TEXT("NetworkManager spawned"));
	}
}

void ARWGameMode::InitializeGameSettings()
{
	ServerHost = TEXT("localhost");
	ServerPort = 8765;
	UE_LOG(LogTemp, Log, TEXT("Game settings initialized: %s:%d"), *ServerHost, ServerPort);
}

void ARWGameMode::SetServerConnection(const FString& Host, int32 Port)
{
	ServerHost = Host;
	ServerPort = Port;
	UE_LOG(LogTemp, Log, TEXT("Server connection updated: %s:%d"), *ServerHost, ServerPort);
}

FString ARWGameMode::GetWebSocketUrl(const FString& Username) const
{
	return FString::Printf(TEXT("ws://%s:%d/ws/%s/1"), *ServerHost, ServerPort, *Username);
}
