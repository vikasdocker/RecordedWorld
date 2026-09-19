#include "RWHUDWidget.h"
#include "Components/TextBlock.h"
#include "Components/ScrollBox.h"
#include "Components/VerticalBox.h"
#include "Components/SizeBox.h"
#include "Styling/SlateTypes.h"

void URWHUDWidget::NativeConstruct()
{
	Super::NativeConstruct();

	if (ConnectionStatusText)
	{
		ConnectionStatusText->SetText(FText::FromString(TEXT("Connecting...")));
		FLinearColor ConnectingColor(1.0f, 0.8f, 0.0f);
		ConnectionStatusText->SetColorAndOpacity(FSlateColor(ConnectingColor));
	}

	if (PlayerCountText)
	{
		PlayerCountText->SetText(FText::FromString(TEXT("Players: 1")));
	}
}

void URWHUDWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);
}

void URWHUDWidget::AddChatMessage(const FString& Sender, const FString& Message)
{
	if (!ChatMessageContainer)
	{
		return;
	}

	UTextBlock* NewMessage = NewObject<UTextBlock>(ChatMessageContainer);
	if (NewMessage)
	{
		const FString FormattedMessage = FString::Printf(TEXT("<%s> %s"), *Sender, *Message);
		NewMessage->SetText(FText::FromString(FormattedMessage));

		FLinearColor SenderColor = (Sender == TEXT("System")) ?
			FLinearColor(1.0f, 0.8f, 0.0f) : FLinearColor(0.0f, 1.0f, 0.53f);
		NewMessage->SetColorAndOpacity(FSlateColor(SenderColor));
		NewMessage->SetFont(FSlateFontInfo(FCoreStyle::GetDefaultFontStyle("Regular", 10)));
		NewMessage->SetAutoWrapText(true);

		ChatMessageContainer->AddChildToVerticalBox(NewMessage);

		if (ChatScrollBox)
		{
			ChatScrollBox->ScrollToEnd();
		}

		TArray<UWidget*> Children = ChatMessageContainer->GetAllChildren();
		while (Children.Num() > MaxChatMessages)
		{
			ChatMessageContainer->RemoveChildAt(0);
			Children = ChatMessageContainer->GetAllChildren();
		}
	}
}

void URWHUDWidget::SetConnectionStatus(bool bConnected, const FString& StatusText)
{
	if (!ConnectionStatusText)
	{
		return;
	}

	ConnectionStatusText->SetText(FText::FromString(StatusText));

	FLinearColor Color = bConnected ?
		FLinearColor(0.0f, 1.0f, 0.53f) : FLinearColor(1.0f, 0.27f, 0.27f);
	ConnectionStatusText->SetColorAndOpacity(FSlateColor(Color));
}

void URWHUDWidget::UpdatePlayerList(const TArray<FPlayerListEntry>& Players)
{
	CachedPlayers = Players;
	RefreshPlayerListBox();
}

void URWHUDWidget::SetMinimapData(const FVector& LocalPos, const TArray<FMinimapPlayerData>& PlayerPositions)
{
}

void URWHUDWidget::RefreshPlayerListBox()
{
	if (!PlayerListBox)
	{
		return;
	}

	PlayerListBox->ClearChildren();

	if (PlayerCountText)
	{
		PlayerCountText->SetText(FText::FromString(FString::Printf(TEXT("Players: %d"), CachedPlayers.Num())));
	}

	for (const auto& Player : CachedPlayers)
	{
		UTextBlock* PlayerEntry = NewObject<UTextBlock>(PlayerListBox);
		if (PlayerEntry)
		{
			const FString EntryText = FString::Printf(TEXT("  %s"), *Player.PlayerName);
			PlayerEntry->SetText(FText::FromString(EntryText));
			PlayerEntry->SetColorAndOpacity(FSlateColor(Player.PlayerColor));
			PlayerEntry->SetFont(FSlateFontInfo(FCoreStyle::GetDefaultFontStyle("Regular", 11)));
			PlayerListBox->AddChildToVerticalBox(PlayerEntry);
		}
	}
}

FReply URWHUDWidget::NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent)
{
	if (InKeyEvent.GetKey() == EKeys::Enter)
	{
		if (bChatInputFocused)
		{
			HandleChatInput();
			bChatInputFocused = false;
			return FReply::Handled();
		}
	}

	if (InKeyEvent.GetKey() == EKeys::T)
	{
		if (!bChatInputFocused)
		{
			bChatInputFocused = true;
			return FReply::Handled();
		}
	}

	if (InKeyEvent.GetKey() == EKeys::Escape)
	{
		if (bChatInputFocused)
		{
			bChatInputFocused = false;
			PendingChatMessage.Empty();
			return FReply::Handled();
		}
	}

	return Super::NativeOnKeyDown(InGeometry, InKeyEvent);
}

void URWHUDWidget::NativeOnFocusLost(const FFocusEvent& InFocusEvent)
{
	Super::NativeOnFocusLost(InFocusEvent);
	bChatInputFocused = false;
}

void URWHUDWidget::HandleChatInput()
{
	if (!PendingChatMessage.IsEmpty())
	{
		OnChatSend.Broadcast(PendingChatMessage);
		PendingChatMessage.Empty();
	}
}
