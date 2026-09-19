#include "RWHUD.h"
#include "RWHUDWidget.h"
#include "NetworkManager.h"
#include "RemotePlayer.h"
#include "RWCharacter.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Kismet/GameplayStatics.h"

ARWHUD::ARWHUD()
{
	PrimaryActorTick.bCanEverTick = true;
}

void ARWHUD::BeginPlay()
{
	Super::BeginPlay();

	if (HUDWidgetClass)
	{
		HUDWidget = CreateWidget<URWHUDWidget>(GetOwningPlayerController(), HUDWidgetClass);
		if (HUDWidget)
		{
			HUDWidget->AddToViewport(100);
			HUDWidget->OnChatSend.AddDynamic(this, &ARWHUD::SendChatMessage);
			UE_LOG(LogTemp, Log, TEXT("HUD widget created"));
		}
	}

	TArray<AActor*> NetworkManagers;
	UGameplayStatics::GetAllActorsOfClass(this, ANetworkManager::StaticClass(), NetworkManagers);
	if (NetworkManagers.Num() > 0)
	{
		CachedNetworkManager = Cast<ANetworkManager>(NetworkManagers[0]);
	}
}

void ARWHUD::DrawHUD()
{
	Super::DrawHUD();
	DrawCrosshair();
	DrawMinimap();
}

void ARWHUD::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	PlayerListRefreshTimer += DeltaTime;
	if (PlayerListRefreshTimer >= PlayerListRefreshInterval)
	{
		PlayerListRefreshTimer = 0.0f;
		RefreshPlayerList();
	}
}

void ARWHUD::AddChatMessage(const FString& Sender, const FString& Message)
{
	if (HUDWidget)
	{
		HUDWidget->AddChatMessage(Sender, Message);
	}
}

void ARWHUD::RefreshPlayerList()
{
	if (!HUDWidget || !CachedNetworkManager)
	{
		return;
	}

	TArray<FPlayerListEntry> Players;

	APawn* LocalPawn = GetOwningPlayerController()->GetPawn();
	if (LocalPawn)
	{
		FPlayerListEntry SelfEntry;
		SelfEntry.PlayerName = TEXT("(you)");
		SelfEntry.PlayerColor = FLinearColor(0.0f, 1.0f, 0.53f);
		Players.Add(SelfEntry);
	}

	const TMap<int32, TObjectPtr<ARemotePlayer>>& RemotePlayers = CachedNetworkManager->GetRemotePlayers();
	for (const auto& Pair : RemotePlayers)
	{
		if (Pair.Value)
		{
			FPlayerListEntry Entry;
			Entry.PlayerName = Pair.Value->Username;
			Entry.PlayerColor = FLinearColor(0.0f, 1.0f, 0.53f);
			Players.Add(Entry);
		}
	}

	HUDWidget->UpdatePlayerList(Players);
}

void ARWHUD::SendChatMessage(const FString& Message)
{
	if (CachedNetworkManager)
	{
		CachedNetworkManager->SendChat(Message);
		AddChatMessage(TEXT("(you)"), Message);
	}
}

void ARWHUD::DrawMinimap()
{
	if (!Canvas)
	{
		return;
	}

	const float MinimapX = Canvas->ClipX - MinimapSize - MinimapMargin;
	const float MinimapY = Canvas->ClipY - MinimapSize - MinimapMargin;

	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.5f), MinimapX, MinimapY, MinimapSize, MinimapSize);

	FLinearColor BorderColor(0.0f, 1.0f, 0.53f, 0.6f);
	DrawRect(BorderColor, MinimapX - 1, MinimapY - 1, MinimapSize + 2, 2);
	DrawRect(BorderColor, MinimapX - 1, MinimapY + MinimapSize - 1, MinimapSize + 2, 2);
	DrawRect(BorderColor, MinimapX - 1, MinimapY, 2, MinimapSize);
	DrawRect(BorderColor, MinimapX + MinimapSize - 1, MinimapY, 2, MinimapSize);

	APawn* LocalPawn = GetOwningPlayerController()->GetPawn();
	if (!LocalPawn)
	{
		return;
	}

	const FVector LocalPos = LocalPawn->GetActorLocation();
	const float CenterX = MinimapX + MinimapSize * 0.5f;
	const float CenterY = MinimapY + MinimapSize * 0.5f;

	DrawRect(FLinearColor(1.0f, 1.0f, 1.0f, 1.0f),
		CenterX - PlayerDotSize * 0.5f, CenterY - PlayerDotSize * 0.5f,
		PlayerDotSize, PlayerDotSize);

	if (!CachedNetworkManager)
	{
		return;
	}

	const TMap<int32, TObjectPtr<ARemotePlayer>>& RemotePlayers = CachedNetworkManager->GetRemotePlayers();
	for (const auto& Pair : RemotePlayers)
	{
		if (!Pair.Value)
		{
			continue;
		}

		const FVector RemotePos = Pair.Value->GetActorLocation();
		const float RelX = (RemotePos.X - LocalPos.X) / ViewRange;
		const float RelY = (RemotePos.Y - LocalPos.Y) / ViewRange;

		if (FMath::Abs(RelX) > 1.0f || FMath::Abs(RelY) > 1.0f)
		{
			continue;
		}

		const float DotX = CenterX + RelX * MinimapSize * 0.5f;
		const float DotY = CenterY - RelY * MinimapSize * 0.5f;

		DrawRect(FLinearColor(0.0f, 1.0f, 0.53f, 1.0f),
			DotX - 2, DotY - 2, 4, 4);
	}
}

void ARWHUD::DrawCrosshair()
{
	if (!Canvas)
	{
		return;
	}

	const float CenterX = Canvas->ClipX * 0.5f;
	const float CenterY = Canvas->ClipY * 0.5f;
	const float Size = 8.0f;
	const float Gap = 3.0f;
	const float Thick = 1.5f;

	FLinearColor CrossColor(0.0f, 1.0f, 0.53f, 0.7f);

	DrawLine(CenterX - Gap - Size, CenterY, CenterX - Gap, CenterY, CrossColor, Thick);
	DrawLine(CenterX + Gap, CenterY, CenterX + Gap + Size, CenterY, CrossColor, Thick);
	DrawLine(CenterX, CenterY - Gap - Size, CenterX, CenterY - Gap, CrossColor, Thick);
	DrawLine(CenterX, CenterY + Gap, CenterX, CenterY + Gap + Size, CrossColor, Thick);
}
