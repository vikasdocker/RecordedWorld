#include "WebSocketManager.h"
#include "WebSocketsModule.h"
#include "IWebSocket.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

UWebSocketManager::UWebSocketManager()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.016f;
}

void UWebSocketManager::BeginPlay()
{
	Super::BeginPlay();
	FModuleManager::Get().LoadModuleChecked<FWebSocketsModule>(TEXT("WebSockets"));
	UE_LOG(LogTemp, Log, TEXT("WebSocketManager initialized"));
}

void UWebSocketManager::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	Disconnect();
	Super::EndPlay(EndPlayReason);
}

void UWebSocketManager::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	if (bIsConnected && LastPingTime > 0.0)
	{
		double CurrentTime = FPlatformTime::Seconds();
		if (CurrentTime - LastPingTime > HeartbeatTimeout)
		{
			UE_LOG(LogTemp, Warning, TEXT("Heartbeat timeout, disconnecting"));
			Disconnect();
		}
	}
}

void UWebSocketManager::Connect(const FString& Url)
{
	if (bIsConnected)
	{
		Disconnect();
	}

	CurrentUrl = Url;
	WebSocket = FWebSocketsModule::Get().CreateWebSocket(Url, TEXT("ws"));

	WebSocket->OnConnected().AddUObject(this, &UWebSocketManager::OnConnected);
	WebSocket->OnConnectionError().AddUObject(this, &UWebSocketManager::OnConnectionError);
	WebSocket->OnClosed().AddUObject(this, &UWebSocketManager::OnClosed);
	WebSocket->OnMessage().AddUObject(this, &UWebSocketManager::OnSocketMessage);

	WebSocket->Connect();
	UE_LOG(LogTemp, Log, TEXT("Connecting to: %s"), *Url);
}

void UWebSocketManager::Disconnect()
{
	if (WebSocket.IsValid() && WebSocket->IsConnected())
	{
		WebSocket->Close();
	}
	bIsConnected = false;
	PlayerId = -1;
	WebSocket.Reset();
}

bool UWebSocketManager::IsConnected() const
{
	return bIsConnected;
}

void UWebSocketManager::OnConnected()
{
	bIsConnected = true;
	LastPingTime = FPlatformTime::Seconds();
	UE_LOG(LogTemp, Log, TEXT("WebSocket connected to: %s"), *CurrentUrl);
}

void UWebSocketManager::OnConnectionError(const FString& Error)
{
	bIsConnected = false;
	OnError.Broadcast(Error);
	UE_LOG(LogTemp, Error, TEXT("WebSocket error: %s"), *Error);
}

void UWebSocketManager::OnClosed(int32 StatusCode, const FString& Reason, bool bWasClean)
{
	bIsConnected = false;
	PlayerId = -1;
	UE_LOG(LogTemp, Log, TEXT("WebSocket closed: %d - %s"), StatusCode, *Reason);
}

void UWebSocketManager::OnSocketMessage(const FString& Message)
{
	TSharedPtr<FJsonObject> JsonMsg;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Message);

	if (!FJsonSerializer::Deserialize(Reader, JsonMsg) || !JsonMsg.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("Failed to parse message: %s"), *Message);
		return;
	}

	FString Type;
	if (!JsonMsg->TryGetStringField(TEXT("type"), Type))
	{
		return;
	}

	if (Type == TEXT("world_state"))          HandleWorldStateJson(JsonMsg);
	else if (Type == TEXT("player_join"))     HandlePlayerJoinJson(JsonMsg);
	else if (Type == TEXT("player_leave"))    HandlePlayerLeaveJson(JsonMsg);
	else if (Type == TEXT("player_move"))     HandlePlayerMoveJson(JsonMsg);
	else if (Type == TEXT("position_correction")) HandlePositionCorrectionJson(JsonMsg);
	else if (Type == TEXT("chat_msg"))        HandleChatMessageJson(JsonMsg);
	else if (Type == TEXT("dm_msg"))          HandleDmMessageJson(JsonMsg);
	else if (Type == TEXT("ping"))            HandlePingJson(JsonMsg);
	else if (Type == TEXT("visibility_changed")) HandleVisibilityChangedJson(JsonMsg);
	else if (Type == TEXT("avatar_changed"))  HandleAvatarChangedJson(JsonMsg);
	else if (Type == TEXT("world_list_resp")) HandleWorldListResponseJson(JsonMsg);
	else if (Type == TEXT("error"))           HandleErrorJson(JsonMsg);
}

void UWebSocketManager::HandleWorldStateJson(const TSharedPtr<FJsonObject>& Data)
{
	FString Output;
	TSharedRef<TJsonWriter<TCHAR>> Writer = TJsonWriterFactory<TCHAR>::Create(&Output);
	FJsonSerializer::Serialize(Data.ToSharedRef(), Writer);
	OnWorldState.Broadcast(Output);

	int32 WorldId = Data->GetNumberField(TEXT("world_id"));
	int32 PlayerCount = Data->GetNumberField(TEXT("player_count"));
	UE_LOG(LogTemp, Log, TEXT("World state: world=%d players=%d"), WorldId, PlayerCount);
}

void UWebSocketManager::HandlePlayerJoinJson(const TSharedPtr<FJsonObject>& Data)
{
	FString Output;
	TSharedRef<TJsonWriter<TCHAR>> Writer = TJsonWriterFactory<TCHAR>::Create(&Output);
	FJsonSerializer::Serialize(Data.ToSharedRef(), Writer);
	OnPlayerJoin.Broadcast(Output);
}

void UWebSocketManager::HandlePlayerLeaveJson(const TSharedPtr<FJsonObject>& Data)
{
	int32 LeavePlayerId = Data->GetNumberField(TEXT("player_id"));
	OnPlayerLeave.Broadcast(LeavePlayerId);
}

void UWebSocketManager::HandlePlayerMoveJson(const TSharedPtr<FJsonObject>& Data)
{
	int32 MovePlayerId = Data->GetNumberField(TEXT("player_id"));
	FString Output;
	TSharedRef<TJsonWriter<TCHAR>> Writer = TJsonWriterFactory<TCHAR>::Create(&Output);
	FJsonSerializer::Serialize(Data.ToSharedRef(), Writer);
	OnPlayerMove.Broadcast(MovePlayerId, Output);
}

void UWebSocketManager::HandlePositionCorrectionJson(const TSharedPtr<FJsonObject>& Data)
{
	FString Output;
	TSharedRef<TJsonWriter<TCHAR>> Writer = TJsonWriterFactory<TCHAR>::Create(&Output);
	FJsonSerializer::Serialize(Data.ToSharedRef(), Writer);
	OnPositionCorrection.Broadcast(Output);
}

void UWebSocketManager::HandleChatMessageJson(const TSharedPtr<FJsonObject>& Data)
{
	FString Output;
	TSharedRef<TJsonWriter<TCHAR>> Writer = TJsonWriterFactory<TCHAR>::Create(&Output);
	FJsonSerializer::Serialize(Data.ToSharedRef(), Writer);
	OnChatMessage.Broadcast(Output);
}

void UWebSocketManager::HandleDmMessageJson(const TSharedPtr<FJsonObject>& Data)
{
	FString Output;
	TSharedRef<TJsonWriter<TCHAR>> Writer = TJsonWriterFactory<TCHAR>::Create(&Output);
	FJsonSerializer::Serialize(Data.ToSharedRef(), Writer);
	OnDmMessage.Broadcast(Output);
}

void UWebSocketManager::HandlePingJson(const TSharedPtr<FJsonObject>& Data)
{
	LastPingTime = FPlatformTime::Seconds();
	SendPong();
}

void UWebSocketManager::HandleVisibilityChangedJson(const TSharedPtr<FJsonObject>& Data)
{
	FString NewVisibility = Data->GetStringField(TEXT("visibility"));
	OnVisibilityChanged.Broadcast(NewVisibility);
}

void UWebSocketManager::HandleAvatarChangedJson(const TSharedPtr<FJsonObject>& Data)
{
	FString NewColor = Data->GetStringField(TEXT("color"));
	OnAvatarChanged.Broadcast(NewColor);
}

void UWebSocketManager::HandleWorldListResponseJson(const TSharedPtr<FJsonObject>& Data)
{
	UE_LOG(LogTemp, Log, TEXT("World list received"));
}

void UWebSocketManager::HandleErrorJson(const TSharedPtr<FJsonObject>& Data)
{
	FString Detail = Data->GetStringField(TEXT("detail"));
	OnError.Broadcast(Detail);
	UE_LOG(LogTemp, Error, TEXT("Server error: %s"), *Detail);
}

void UWebSocketManager::SendJsonMessage(const TSharedPtr<FJsonObject>& JsonMessage)
{
	if (!bIsConnected || !WebSocket.IsValid() || !WebSocket->IsConnected())
	{
		return;
	}
	FString OutputString;
	TSharedRef<TJsonWriter<TCHAR>> Writer = TJsonWriterFactory<TCHAR>::Create(&OutputString);
	FJsonSerializer::Serialize(JsonMessage.ToSharedRef(), Writer);
	WebSocket->Send(OutputString);
}

void UWebSocketManager::SendPositionUpdate(float X, float Y, float Z, float Rotation)
{
	double CurrentTime = FPlatformTime::Seconds();
	if (CurrentTime - LastPositionUpdateTime < PositionUpdateRateLimit)
	{
		return;
	}
	LastPositionUpdateTime = CurrentTime;

	TSharedPtr<FJsonObject> Msg = MakeShareable(new FJsonObject);
	Msg->SetStringField(TEXT("type"), TEXT("position_update"));

	TSharedPtr<FJsonObject> Pos = MakeShareable(new FJsonObject);
	Pos->SetNumberField(TEXT("x"), X);
	Pos->SetNumberField(TEXT("y"), Y);
	Pos->SetNumberField(TEXT("z"), Z);
	Msg->SetObjectField(TEXT("position"), Pos);
	Msg->SetNumberField(TEXT("rotation"), Rotation);

	SendJsonMessage(Msg);
}

void UWebSocketManager::SendChatMessage(const FString& MessageText)
{
	TSharedPtr<FJsonObject> Msg = MakeShareable(new FJsonObject);
	Msg->SetStringField(TEXT("type"), TEXT("chat"));
	Msg->SetStringField(TEXT("message"), MessageText);
	SendJsonMessage(Msg);
}

void UWebSocketManager::SendDirectMessage(const FString& ToUsername, const FString& MessageText)
{
	TSharedPtr<FJsonObject> Msg = MakeShareable(new FJsonObject);
	Msg->SetStringField(TEXT("type"), TEXT("dm"));
	Msg->SetStringField(TEXT("to"), ToUsername);
	Msg->SetStringField(TEXT("message"), MessageText);
	SendJsonMessage(Msg);
}

void UWebSocketManager::SetVisibility(const FString& Visibility)
{
	TSharedPtr<FJsonObject> Msg = MakeShareable(new FJsonObject);
	Msg->SetStringField(TEXT("type"), TEXT("set_visibility"));
	Msg->SetStringField(TEXT("visibility"), Visibility);
	SendJsonMessage(Msg);
}

void UWebSocketManager::SetAvatarColor(const FString& ColorHex)
{
	TSharedPtr<FJsonObject> Msg = MakeShareable(new FJsonObject);
	Msg->SetStringField(TEXT("type"), TEXT("set_avatar"));
	Msg->SetStringField(TEXT("color"), ColorHex);
	SendJsonMessage(Msg);
}

void UWebSocketManager::RequestWorldList()
{
	TSharedPtr<FJsonObject> Msg = MakeShareable(new FJsonObject);
	Msg->SetStringField(TEXT("type"), TEXT("world_list"));
	SendJsonMessage(Msg);
}

void UWebSocketManager::SendVoiceState(bool bActive)
{
	TSharedPtr<FJsonObject> Msg = MakeShareable(new FJsonObject);
	Msg->SetStringField(TEXT("type"), TEXT("voice"));
	Msg->SetBoolField(TEXT("active"), bActive);
	SendJsonMessage(Msg);
}

void UWebSocketManager::SendPong()
{
	TSharedPtr<FJsonObject> Msg = MakeShareable(new FJsonObject);
	Msg->SetStringField(TEXT("type"), TEXT("pong"));
	SendJsonMessage(Msg);
}
