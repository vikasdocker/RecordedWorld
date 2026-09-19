#include "NetworkManager.h"
#include "WebSocketManager.h"
#include "RemotePlayer.h"
#include "RWCharacter.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

ANetworkManager::ANetworkManager()
{
	PrimaryActorTick.bCanEverTick = true;

	WebSocket = CreateDefaultSubobject<UWebSocketManager>(TEXT("WebSocket"));
}

void ANetworkManager::BeginPlay()
{
	Super::BeginPlay();

	WebSocket->OnWorldState.AddDynamic(this, &ANetworkManager::HandleWorldState);
	WebSocket->OnPlayerJoin.AddDynamic(this, &ANetworkManager::HandlePlayerJoin);
	WebSocket->OnPlayerLeave.AddDynamic(this, &ANetworkManager::HandlePlayerLeave);
	WebSocket->OnPlayerMove.AddDynamic(this, &ANetworkManager::HandlePlayerMove);
	WebSocket->OnPositionCorrection.AddDynamic(this, &ANetworkManager::HandlePositionCorrection);
	WebSocket->OnChatMessage.AddDynamic(this, &ANetworkManager::HandleChatMessage);
	WebSocket->OnError.AddDynamic(this, &ANetworkManager::HandleError);

	LocalCharacter = Cast<ARWCharacter>(UGameplayStatics::GetPlayerCharacter(this, 0));

	ConnectToServer();
}

void ANetworkManager::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	if (!WebSocket->IsConnected())
	{
		return;
	}

	if (LocalCharacter)
	{
		PositionSendTimer += DeltaTime;
		if (PositionSendTimer >= PositionSendInterval)
		{
			PositionSendTimer = 0.0f;
			const FVector Pos = LocalCharacter->GetActorLocation();
			const float Rot = LocalCharacter->GetActorRotation().Yaw;
			WebSocket->SendPositionUpdate(Pos.X, Pos.Y, Pos.Z, Rot);
		}
	}
}

void ANetworkManager::ConnectToServer()
{
	const FString Url = GetWebSocketUrl();
	UE_LOG(LogTemp, Log, TEXT("NetworkManager connecting: %s"), *Url);
	WebSocket->Connect(Url);
}

void ANetworkManager::Disconnect()
{
	WebSocket->Disconnect();

	for (auto& Pair : RemotePlayers)
	{
		if (Pair.Value)
		{
			Pair.Value->Destroy();
		}
	}
	RemotePlayers.Empty();
}

bool ANetworkManager::IsConnected() const
{
	return WebSocket->IsConnected();
}

void ANetworkManager::SendChat(const FString& Message)
{
	WebSocket->SendChatMessage(Message);
}

void ANetworkManager::SendDirectMessage(const FString& ToPlayer, const FString& Message)
{
	WebSocket->SendDirectMessage(ToPlayer, Message);
}

FString ANetworkManager::GetWebSocketUrl() const
{
	return FString::Printf(TEXT("ws://%s:%d/ws/%s/%s"), *ServerHost, ServerPort, *Username, *WorldId);
}

void ANetworkManager::HandleWorldState(const FString& JsonString)
{
	TSharedPtr<FJsonObject> JsonMsg;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
	if (!FJsonSerializer::Deserialize(Reader, JsonMsg) || !JsonMsg.IsValid())
	{
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* PlayersArray;
	if (!JsonMsg->TryGetArrayField(TEXT("players"), PlayersArray))
	{
		return;
	}

	for (const auto& PlayerVal : *PlayersArray)
	{
		const TSharedPtr<FJsonObject>& PlayerObj = PlayerVal->AsObject();
		if (!PlayerObj.IsValid())
		{
			continue;
		}

		const int32 PlayerId = PlayerObj->GetNumberField(TEXT("id"));
		const FString PlayerName = PlayerObj->GetStringField(TEXT("username"));

		if (PlayerName == Username)
		{
			continue;
		}

		if (RemotePlayers.Contains(PlayerId))
		{
			continue;
		}

		const FVector Pos = ParsePosition(PlayerObj->GetObjectField(TEXT("position")));
		const float Rot = PlayerObj->GetNumberField(TEXT("rotation"));

		FLinearColor Color = FLinearColor(0.0f, 1.0f, 0.53f);
		if (PlayerObj->HasField(TEXT("color")))
		{
			Color = ParseHexColor(PlayerObj->GetStringField(TEXT("color")));
		}

		FActorSpawnParameters SpawnParams;
		SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		ARemotePlayer* NewPlayer = GetWorld()->SpawnActor<ARemotePlayer>(
			ARemotePlayer::StaticClass(), Pos, FRotator(0.0f, Rot, 0.0f), SpawnParams);

		if (NewPlayer)
		{
			NewPlayer->ServerPlayerId = PlayerId;
			NewPlayer->InitPlayer(PlayerName, Color);
			RemotePlayers.Add(PlayerId, NewPlayer);
			UE_LOG(LogTemp, Log, TEXT("World state: spawned player '%s' (id=%d) at %s"),
				*PlayerName, PlayerId, *Pos.ToString());
		}
	}

	UE_LOG(LogTemp, Log, TEXT("World state: %d remote players loaded"), RemotePlayers.Num());
}

void ANetworkManager::HandlePlayerJoin(const FString& JsonString)
{
	TSharedPtr<FJsonObject> JsonMsg;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
	if (!FJsonSerializer::Deserialize(Reader, JsonMsg) || !JsonMsg.IsValid())
	{
		return;
	}

	const TSharedPtr<FJsonObject>& PlayerObj = JsonMsg->GetObjectField(TEXT("player"));
	const int32 PlayerId = PlayerObj->GetNumberField(TEXT("id"));
	const FString PlayerName = PlayerObj->GetStringField(TEXT("username"));

	if (PlayerName == Username)
	{
		return;
	}

	if (RemotePlayers.Contains(PlayerId))
	{
		return;
	}

	const FVector Pos = ParsePosition(PlayerObj->GetObjectField(TEXT("position")));
	const float Rot = PlayerObj->HasField(TEXT("rotation")) ? PlayerObj->GetNumberField(TEXT("rotation")) : 0.0f;

	FLinearColor Color = FLinearColor(0.0f, 1.0f, 0.53f);
	if (PlayerObj->HasField(TEXT("color")))
	{
		Color = ParseHexColor(PlayerObj->GetStringField(TEXT("color")));
	}

	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ARemotePlayer* NewPlayer = GetWorld()->SpawnActor<ARemotePlayer>(
		ARemotePlayer::StaticClass(), Pos, FRotator(0.0f, Rot, 0.0f), SpawnParams);

	if (NewPlayer)
	{
		NewPlayer->ServerPlayerId = PlayerId;
		NewPlayer->InitPlayer(PlayerName, Color);
		RemotePlayers.Add(PlayerId, NewPlayer);
		UE_LOG(LogTemp, Log, TEXT("Player joined: '%s' (id=%d)"), *PlayerName, PlayerId);
	}
}

void ANetworkManager::HandlePlayerLeave(int32 PlayerId)
{
	TObjectPtr<ARemotePlayer>* Found = RemotePlayers.Find(PlayerId);
	if (Found && *Found)
	{
		UE_LOG(LogTemp, Log, TEXT("Player left: '%s' (id=%d)"), *(*Found)->Username, PlayerId);
		(*Found)->Destroy();
	}
	RemotePlayers.Remove(PlayerId);
}

void ANetworkManager::HandlePlayerMove(int32 PlayerId, const FString& JsonString)
{
	TSharedPtr<FJsonObject> JsonMsg;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
	if (!FJsonSerializer::Deserialize(Reader, JsonMsg) || !JsonMsg.IsValid())
	{
		return;
	}

	TObjectPtr<ARemotePlayer>* Found = RemotePlayers.Find(PlayerId);
	if (!Found || !(*Found))
	{
		return;
	}

	const FVector Pos = ParsePosition(JsonMsg->GetObjectField(TEXT("position")));
	const float Rot = JsonMsg->GetNumberField(TEXT("rotation"));

	(*Found)->UpdatePosition(Pos, Rot);
}

void ANetworkManager::HandlePositionCorrection(const FString& JsonString)
{
	TSharedPtr<FJsonObject> JsonMsg;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
	if (!FJsonSerializer::Deserialize(Reader, JsonMsg) || !JsonMsg.IsValid())
	{
		return;
	}

	if (LocalCharacter)
	{
		const FVector CorrectedPos = ParsePosition(JsonMsg->GetObjectField(TEXT("position")));
		LocalCharacter->SetActorLocation(CorrectedPos);
		UE_LOG(LogTemp, Warning, TEXT("Position corrected to %s"), *CorrectedPos.ToString());
	}
}

void ANetworkManager::HandleChatMessage(const FString& JsonString)
{
	TSharedPtr<FJsonObject> JsonMsg;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
	if (!FJsonSerializer::Deserialize(Reader, JsonMsg) || !JsonMsg.IsValid())
	{
		return;
	}

	const FString Sender = JsonMsg->GetStringField(TEXT("username"));
	const FString Message = JsonMsg->GetStringField(TEXT("message"));
	UE_LOG(LogTemp, Log, TEXT("[Chat] %s: %s"), *Sender, *Message);
}

void ANetworkManager::HandleError(const FString& ErrorMessage)
{
	UE_LOG(LogTemp, Error, TEXT("Network error: %s"), *ErrorMessage);
}

FVector ANetworkManager::ParsePosition(const TSharedPtr<FJsonObject>& PosObj) const
{
	if (!PosObj.IsValid())
	{
		return FVector::ZeroVector;
	}
	return FVector(
		PosObj->GetNumberField(TEXT("x")),
		PosObj->GetNumberField(TEXT("y")),
		PosObj->GetNumberField(TEXT("z"))
	);
}

FLinearColor ANetworkManager::ParseHexColor(const FString& Hex) const
{
	FString CleanHex = Hex;
	if (CleanHex.StartsWith(TEXT("#")))
	{
		CleanHex.RemoveAt(0);
	}

	if (CleanHex.Len() == 6)
	{
		const int32 R = FCString::Strtoi(*CleanHex.Left(2), nullptr, 16);
		const int32 G = FCString::Strtoi(*CleanHex.Mid(2, 2), nullptr, 16);
		const int32 B = FCString::Strtoi(*CleanHex.Right(2), nullptr, 16);
		return FLinearColor(R / 255.0f, G / 255.0f, B / 255.0f);
	}

	return FLinearColor(0.0f, 1.0f, 0.53f);
}
