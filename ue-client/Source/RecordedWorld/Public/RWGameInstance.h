#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "RWGameInstance.generated.h"

UCLASS()
class RECORDEDWORLD_API URWGameInstance : public UGameInstance
{
	GENERATED_BODY()

public:
	URWGameInstance();

	virtual void Init() override;
	virtual void Shutdown() override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Connection")
	FString ServerHost = TEXT("localhost");

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Connection")
	int32 ServerPort = 8765;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Connection")
	FString Username = TEXT("Player");

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Connection")
	FString WorldId = TEXT("1");

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Connection")
	bool bIsConnected = false;

	UFUNCTION(BlueprintCallable, Category = "Connection")
	void SetConnectionParams(const FString& Host, int32 Port, const FString& PlayerName, const FString& World);

	UFUNCTION(BlueprintCallable, Category = "Connection")
	FString GetWebSocketUrl() const;

	UFUNCTION(BlueprintCallable, Category = "Connection")
	void SetConnected(bool bConnected);
};
