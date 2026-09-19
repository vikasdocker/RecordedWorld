#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "WebSocketManager.generated.h"

// Forward declare - actual includes in .cpp
class FJsonObject;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnPlayerJoin, const FString&, PlayerJsonString);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnPlayerLeave, int32, PlayerId);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnPlayerMove, int32, PlayerId, const FString&, MoveJsonString);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnChatMessage, const FString&, ChatJsonString);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnDmMessage, const FString&, DmJsonString);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWorldState, const FString&, WorldStateJsonString);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnPositionCorrection, const FString&, CorrectionJsonString);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnError, const FString&, ErrorMessage);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnVisibilityChanged, const FString&, NewVisibility);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAvatarChanged, const FString&, NewColor);

UCLASS(ClassGroup=(Network), meta=(BlueprintSpawnableComponent))
class RECORDEDWORLD_API UWebSocketManager : public UActorComponent
{
	GENERATED_BODY()

public:
	UWebSocketManager();

	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UFUNCTION(BlueprintCallable, Category = "WebSocket")
	void Connect(const FString& Url);

	UFUNCTION(BlueprintCallable, Category = "WebSocket")
	void Disconnect();

	UFUNCTION(BlueprintPure, Category = "WebSocket")
	bool IsConnected() const;

	UFUNCTION(BlueprintCallable, Category = "WebSocket|Messages")
	void SendPositionUpdate(float X, float Y, float Z, float Rotation);

	UFUNCTION(BlueprintCallable, Category = "WebSocket|Messages")
	void SendChatMessage(const FString& Message);

	UFUNCTION(BlueprintCallable, Category = "WebSocket|Messages")
	void SendDirectMessage(const FString& ToUsername, const FString& Message);

	UFUNCTION(BlueprintCallable, Category = "WebSocket|Messages")
	void SetVisibility(const FString& Visibility);

	UFUNCTION(BlueprintCallable, Category = "WebSocket|Messages")
	void SetAvatarColor(const FString& ColorHex);

	UFUNCTION(BlueprintCallable, Category = "WebSocket|Messages")
	void RequestWorldList();

	UFUNCTION(BlueprintCallable, Category = "WebSocket|Messages")
	void SendVoiceState(bool bActive);

	UPROPERTY(BlueprintAssignable, Category = "WebSocket|Events")
	FOnPlayerJoin OnPlayerJoin;

	UPROPERTY(BlueprintAssignable, Category = "WebSocket|Events")
	FOnPlayerLeave OnPlayerLeave;

	UPROPERTY(BlueprintAssignable, Category = "WebSocket|Events")
	FOnPlayerMove OnPlayerMove;

	UPROPERTY(BlueprintAssignable, Category = "WebSocket|Events")
	FOnChatMessage OnChatMessage;

	UPROPERTY(BlueprintAssignable, Category = "WebSocket|Events")
	FOnDmMessage OnDmMessage;

	UPROPERTY(BlueprintAssignable, Category = "WebSocket|Events")
	FOnWorldState OnWorldState;

	UPROPERTY(BlueprintAssignable, Category = "WebSocket|Events")
	FOnPositionCorrection OnPositionCorrection;

	UPROPERTY(BlueprintAssignable, Category = "WebSocket|Events")
	FOnError OnError;

	UPROPERTY(BlueprintAssignable, Category = "WebSocket|Events")
	FOnVisibilityChanged OnVisibilityChanged;

	UPROPERTY(BlueprintAssignable, Category = "WebSocket|Events")
	FOnAvatarChanged OnAvatarChanged;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WebSocket|State")
	FString CurrentUrl;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WebSocket|State")
	bool bIsConnected = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WebSocket|State")
	int32 PlayerId = -1;

private:
	TSharedPtr<class IWebSocket> WebSocket;

	void OnConnected();
	void OnConnectionError(const FString& Error);
	void OnClosed(int32 StatusCode, const FString& Reason, bool bWasClean);
	void OnSocketMessage(const FString& Message);

	void HandleWorldStateJson(const TSharedPtr<FJsonObject>& Data);
	void HandlePlayerJoinJson(const TSharedPtr<FJsonObject>& Data);
	void HandlePlayerLeaveJson(const TSharedPtr<FJsonObject>& Data);
	void HandlePlayerMoveJson(const TSharedPtr<FJsonObject>& Data);
	void HandlePositionCorrectionJson(const TSharedPtr<FJsonObject>& Data);
	void HandleChatMessageJson(const TSharedPtr<FJsonObject>& Data);
	void HandleDmMessageJson(const TSharedPtr<FJsonObject>& Data);
	void HandlePingJson(const TSharedPtr<FJsonObject>& Data);
	void HandleVisibilityChangedJson(const TSharedPtr<FJsonObject>& Data);
	void HandleAvatarChangedJson(const TSharedPtr<FJsonObject>& Data);
	void HandleWorldListResponseJson(const TSharedPtr<FJsonObject>& Data);
	void HandleErrorJson(const TSharedPtr<FJsonObject>& Data);

	void SendJsonMessage(const TSharedPtr<FJsonObject>& JsonMessage);
	void SendPong();

	double LastPositionUpdateTime = 0.0;
	static constexpr double PositionUpdateRateLimit = 0.1;

	double LastPingTime = 0.0;
	static constexpr double HeartbeatTimeout = 60.0;
};
