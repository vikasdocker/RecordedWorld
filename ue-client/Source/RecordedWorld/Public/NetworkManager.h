#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "NetworkManager.generated.h"

class UWebSocketManager;
class ARemotePlayer;
class ARWCharacter;

UCLASS()
class RECORDEDWORLD_API ANetworkManager : public AActor
{
	GENERATED_BODY()

public:
	ANetworkManager();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaTime) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Network")
	TObjectPtr<UWebSocketManager> WebSocket;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Network")
	FString ServerHost = TEXT("localhost");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Network")
	int32 ServerPort = 8765;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Network")
	FString Username = TEXT("Player");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Network")
	FString WorldId = TEXT("1");

	UFUNCTION(BlueprintCallable, Category = "Network")
	void ConnectToServer();

	UFUNCTION(BlueprintCallable, Category = "Network")
	void Disconnect();

	UFUNCTION(BlueprintPure, Category = "Network")
	bool IsConnected() const;

	UFUNCTION(BlueprintCallable, Category = "Network")
	void SendChat(const FString& Message);

	UFUNCTION(BlueprintCallable, Category = "Network")
	void SendDirectMessage(const FString& ToPlayer, const FString& Message);

	const TMap<int32, TObjectPtr<ARemotePlayer>>& GetRemotePlayers() const { return RemotePlayers; }

private:
	UFUNCTION()
	void HandleWorldState(const FString& JsonString);

	UFUNCTION()
	void HandlePlayerJoin(const FString& JsonString);

	UFUNCTION()
	void HandlePlayerLeave(int32 PlayerId);

	UFUNCTION()
	void HandlePlayerMove(int32 PlayerId, const FString& JsonString);

	UFUNCTION()
	void HandlePositionCorrection(const FString& JsonString);

	UFUNCTION()
	void HandleChatMessage(const FString& JsonString);

	UFUNCTION()
	void HandleError(const FString& ErrorMessage);

	FString GetWebSocketUrl() const;
	FVector ParsePosition(const TSharedPtr<FJsonObject>& PosObj) const;
	FLinearColor ParseHexColor(const FString& Hex) const;

	UPROPERTY()
	TMap<int32, TObjectPtr<ARemotePlayer>> RemotePlayers;

	UPROPERTY()
	TObjectPtr<ARWCharacter> LocalCharacter;

	float PositionSendTimer = 0.0f;
	static constexpr float PositionSendInterval = 0.1f;
};
