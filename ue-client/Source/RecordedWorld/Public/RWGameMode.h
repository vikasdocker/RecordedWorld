#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "RWGameMode.generated.h"

UCLASS()
class RECORDEDWORLD_API ARWGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ARWGameMode();

	virtual void StartPlay() override;
	virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;

	UPROPERTY(EditDefaultsOnly, Category = "Server")
	FString ServerHost = TEXT("localhost");

	UPROPERTY(EditDefaultsOnly, Category = "Server")
	int32 ServerPort = 8765;

	UPROPERTY(EditDefaultsOnly, Category = "World")
	FString DefaultWorldId = TEXT("1");

	UFUNCTION(BlueprintCallable, Category = "Server")
	void SetServerConnection(const FString& Host, int32 Port);

	UFUNCTION(BlueprintPure, Category = "Server")
	FString GetWebSocketUrl(const FString& Username) const;

private:
	void InitializeGameSettings();
};
