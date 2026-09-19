#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "RWHUDWidget.generated.h"

class UTextBlock;
class UScrollBox;
class UVerticalBox;
class USizeBox;

USTRUCT(BlueprintType)
struct FPlayerListEntry
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FString PlayerName = TEXT("");

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FLinearColor PlayerColor = FLinearColor::White;
};

USTRUCT(BlueprintType)
struct FMinimapPlayerData
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector Position;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FLinearColor Color;
};

UCLASS()
class RECORDEDWORLD_API URWHUDWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	virtual void NativeConstruct() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

	UFUNCTION(BlueprintCallable, Category = "HUD")
	void AddChatMessage(const FString& Sender, const FString& Message);

	UFUNCTION(BlueprintCallable, Category = "HUD")
	void SetConnectionStatus(bool bConnected, const FString& StatusText);

	UFUNCTION(BlueprintCallable, Category = "HUD")
	void UpdatePlayerList(const TArray<FPlayerListEntry>& Players);

	UFUNCTION(BlueprintCallable, Category = "HUD")
	void SetMinimapData(const FVector& LocalPos, const TArray<FMinimapPlayerData>& PlayerPositions);

	UPROPERTY(meta = (BindWidget))
	TObjectPtr<UTextBlock> ConnectionStatusText;

	UPROPERTY(meta = (BindWidget))
	TObjectPtr<UTextBlock> PlayerCountText;

	UPROPERTY(meta = (BindWidget))
	TObjectPtr<UScrollBox> ChatScrollBox;

	UPROPERTY(meta = (BindWidget))
	TObjectPtr<UVerticalBox> ChatMessageContainer;

	UPROPERTY(meta = (BindWidget))
	TObjectPtr<UVerticalBox> PlayerListBox;

	UPROPERTY(meta = (BindWidget))
	TObjectPtr<USizeBox> MinimapSizeBox;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "HUD|Chat")
	int32 MaxChatMessages = 50;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "HUD|Chat")
	FString PendingChatMessage;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "HUD|Chat")
	bool bChatInputFocused = false;

	DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnChatSend, const FString&, Message);
	UPROPERTY(BlueprintAssignable, Category = "HUD|Chat")
	FOnChatSend OnChatSend;

protected:
	virtual FReply NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent) override;
	virtual void NativeOnFocusLost(const FFocusEvent& InFocusEvent) override;

private:
	void HandleChatInput();
	void RefreshPlayerListBox();

	UPROPERTY()
	TArray<FPlayerListEntry> CachedPlayers;

	bool bChatVisible = true;
};
