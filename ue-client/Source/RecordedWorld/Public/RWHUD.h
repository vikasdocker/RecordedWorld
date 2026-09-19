#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "RWHUD.generated.h"

class URWHUDWidget;
class ANetworkManager;

UCLASS()
class RECORDEDWORLD_API ARWHUD : public AHUD
{
	GENERATED_BODY()

public:
	ARWHUD();

	virtual void BeginPlay() override;
	virtual void DrawHUD() override;
	virtual void Tick(float DeltaTime) override;

	UPROPERTY(EditDefaultsOnly, Category = "HUD")
	TSubclassOf<URWHUDWidget> HUDWidgetClass;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "HUD")
	TObjectPtr<URWHUDWidget> HUDWidget;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "HUD")
	TObjectPtr<ANetworkManager> CachedNetworkManager;

	UFUNCTION(BlueprintCallable, Category = "HUD")
	void AddChatMessage(const FString& Sender, const FString& Message);

	UFUNCTION(BlueprintCallable, Category = "HUD")
	void RefreshPlayerList();

	UFUNCTION(BlueprintCallable, Category = "HUD")
	void SendChatMessage(const FString& Message);

private:
	void DrawMinimap();
	void DrawCrosshair();

	float MinimapSize = 160.0f;
	float MinimapMargin = 20.0f;
	float MinimapScale = 0.5f;
	float PlayerDotSize = 4.0f;
	float ViewRange = 500.0f;

	float PlayerListRefreshTimer = 0.0f;
	static constexpr float PlayerListRefreshInterval = 1.0f;
};
